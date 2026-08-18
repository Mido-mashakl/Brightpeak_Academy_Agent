"""
Brightpeak Academy — Retrieval Evaluation (Legacy + Course Material + Refusal)

This benchmark intentionally keeps the original 12 policy questions and adds
course-scoped retrieval tests grounded in the actual files under
Phase-2/documents/course_materials/.

It also includes wrong-course and genuinely out-of-scope questions. Those are
negative tests: the retrieval layer may return weak semantic neighbors, but
Self-RAG should reject them and the teaching agent must not answer from general
LLM knowledge.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

EVAL_DIR=Path(__file__).resolve().parent
PHASE2=EVAL_DIR.parent
sys.path.insert(0,str(PHASE2/'rag'))
from ingestion import ingest
from naive_rag import NaiveRAG
from hybrid_rag import HybridRAG
from agentic_rag import AgenticRAG
from graph_rag import GraphRAG
from self_rag import SelfRAGVerifier

ARCHS=('naive','hybrid','agentic','graph')

def load_questions():
    return json.loads((EVAL_DIR/'questions.json').read_text(encoding='utf-8'))

def approx_tokens(text): return max(1,len(text)//4)

def _norm(path: str) -> str:
    """Normalise path separators so Windows-built stores compare correctly."""
    return path.replace('\\', '/').lower()

def source_hit(hits, expected):
    if not expected: return False
    got=[_norm((h.get('metadata') or {}).get('source_file','')) for h in hits]
    return any(any(_norm(e) in g for e in expected) for g in got)

def source_recall(hits, expected):
    if not expected: return 0.0
    got=[_norm((h.get('metadata') or {}).get('source_file','')) for h in hits]
    return sum(any(_norm(e) in g for g in got) for e in expected)/len(expected)

def mrr(hits, expected):
    for rank,h in enumerate(hits,1):
        src=_norm((h.get('metadata') or {}).get('source_file') or '')
        if any(_norm(e) in src for e in expected): return 1.0/rank
    return 0.0

def keyword_coverage(ctx, expected):
    if not expected:return 0.0
    low=ctx.lower()
    return sum(k.lower() in low for k in expected)/len(expected)

def course_isolated(hits, course_id):
    return bool(hits) and all((h.get('metadata') or {}).get('course_id')==course_id and (h.get('metadata') or {}).get('content_type')=='course_material' for h in hits)

def evaluate_one(rag,q,verifier):
    where=None
    if q['scope']=='course_material':
        where={'content_type':'course_material','course_id':q['course_id']}
    t=time.perf_counter(); result=rag.run(q['question'],where=where); latency=time.perf_counter()-t
    hits=result.get('hits',[]); ctx=result.get('context','')
    verification=verifier.verify(q['question'],[h.get('document','') for h in hits])
    is_reject=q['expected_action']=='reject'
    if is_reject:
        passed=(verification.action!='pass')
        # No forbidden source is allowed for wrong-course/out-of-scope cases.
        forbidden=bool(q.get('expected_sources')) and any(
            any(e.lower() in ((h.get('metadata') or {}).get('source_file','')).lower() for e in q['expected_sources'])
            for h in hits)
        return {'id':q['id'],'category':q['category'],'passed':passed and not forbidden,
                'verification_action':verification.action,'source_hit':source_hit(hits,q.get('expected_sources',[])),
                'forbidden_leakage':forbidden,'latency_s':round(latency,4),'tokens':approx_tokens(ctx),'n_hits':len(hits)}
    expected_src=q.get('expected_sources',[])
    # Policy questions have empty expected_sources; fall back to keyword_coverage
    # (same metric as the legacy benchmark) so those 12 questions score correctly.
    if q['scope']=='policy' and not expected_src:
        kw_score=keyword_coverage(ctx,q.get('expected_keywords',[]))
        passed=kw_score>=0.5
    else:
        passed=source_hit(hits,expected_src)
    return {'id':q['id'],'category':q['category'],'passed':passed,
            'source_hit':source_hit(hits,expected_src),
            'source_recall':round(source_recall(hits,expected_src),3),
            'mrr':round(mrr(hits,expected_src),3),
            'keyword_coverage':round(keyword_coverage(ctx,q.get('expected_keywords',[])),3),
            'course_isolated':course_isolated(hits,q['course_id']) if q['scope']=='course_material' else None,
            'verification_action':verification.action,'latency_s':round(latency,4),'tokens':approx_tokens(ctx),'n_hits':len(hits)}

def run_eval():
    store=ingest(reset=True)
    rag={'naive':NaiveRAG(store,top_k=5),'hybrid':HybridRAG(store,top_k=5),
         'agentic':AgenticRAG(store,top_k=5,max_hops=3),'graph':GraphRAG(store,top_k=5)}
    qs=load_questions(); verifier=SelfRAGVerifier(); all_results=[]
    for name,obj in rag.items():
        rows=[evaluate_one(obj,q,verifier) for q in qs]
        positives=[r for r,q in zip(rows,qs) if q['expected_action']=='retrieve']
        negatives=[r for r,q in zip(rows,qs) if q['expected_action']=='reject']
        course_pos=[r for r,q in zip(rows,qs) if q['scope']=='course_material' and q['expected_action']=='retrieve']
        course_neg=[r for r,q in zip(rows,qs) if q['scope']=='course_material' and q['expected_action']=='reject']
        all_results.append({'architecture':name,
          'overall_pass_rate':round(sum(r['passed'] for r in rows)/len(rows),3),
          'policy_pass_rate':round(sum(r['passed'] for r,q in zip(rows,qs) if q['scope']=='policy')/sum(q['scope']=='policy' for q in qs),3),
          'course_source_hit_at_5':round(sum(r.get('source_hit',False) for r in course_pos)/len(course_pos),3),
          'course_mrr':round(sum(r.get('mrr',0) for r in course_pos)/len(course_pos),3),
          'course_keyword_coverage':round(sum(r.get('keyword_coverage',0) for r in course_pos)/len(course_pos),3),
          'course_isolation_rate':round(sum(r.get('course_isolated',False) for r in course_pos)/len(course_pos),3),
          'negative_refusal_rate':round(sum(r['passed'] for r in negatives)/len(negatives),3),
          'course_negative_refusal_rate':round(sum(r['passed'] for r in course_neg)/len(course_neg),3),
          'avg_latency_s':round(sum(r['latency_s'] for r in rows)/len(rows),4),
          'avg_context_tokens':round(sum(r['tokens'] for r in rows)/len(rows)),
          'per_question':rows})
    (EVAL_DIR/'results.json').write_text(json.dumps(all_results,indent=2),encoding='utf-8')
    md=['# Retrieval Evaluation — Legacy + Course Material','','The benchmark keeps the original 12 policy questions and adds 50 course-material cases: grounded, wrong-course, and out-of-scope refusal tests.','', '| Architecture | Overall | Policy | Course Hit@5 | Course MRR | Course Isolation | Negative Refusal | Avg Latency |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in all_results:
        md.append(f"| {r['architecture']} | {r['overall_pass_rate']:.0%} | {r['policy_pass_rate']:.0%} | {r['course_source_hit_at_5']:.0%} | {r['course_mrr']:.3f} | {r['course_isolation_rate']:.0%} | {r['negative_refusal_rate']:.0%} | {r['avg_latency_s']:.3f}s |")
    md += ['', '## Acceptance criteria','', '- A grounded course question should retrieve at least one expected source.', '- Every course result must stay inside the requested `course_id` and `content_type=course_material`.', '- Wrong-course and out-of-scope cases should be rejected by Self-RAG; the teaching agent must not answer from general knowledge.', '- The original policy benchmark remains part of the same evaluation so regressions are visible.','']
    (EVAL_DIR/'comparison_table.md').write_text('\n'.join(md),encoding='utf-8')
    print('\n'.join(md))
    return all_results

if __name__=='__main__': run_eval()