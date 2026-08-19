-- ============================================================
-- Brightpeak Academy — Seed Data (SQLite)
-- Run after schema.sql
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- Instructors
-- ------------------------------------------------------------
INSERT INTO Instructors (instructor_id, name, email) VALUES
    (1, 'Laila Hassan',     'laila.hassan@brightpeak.edu'),
    (2, 'Omar El-Sayed',    'omar.elsayed@brightpeak.edu'),
    (3, 'Karim Fathy',      'karim.fathy@brightpeak.edu'),
    (4, 'Nourhan Adel',     'nourhan.adel@brightpeak.edu'),
    (5, 'Youssef Tarek',    'youssef.tarek@brightpeak.edu'),
    (6,  'Mona Reda',       'mona.reda@brightpeak.edu'),
    (7,  'Tarek Younis',    'tarek.younis@brightpeak.edu'),
    (8,  'Hana Adly',       'hana.adly@brightpeak.edu'),
    (9,  'Sameh Nabil',     'sameh.nabil@brightpeak.edu'),
    (10, 'Dina Farouk',     'dina.farouk@brightpeak.edu');
-- ------------------------------------------------------------
-- DeptHeads (Faculty Hiring HITL reviewers)
-- ------------------------------------------------------------
INSERT INTO DeptHeads (dept_head_id, name, email, department) VALUES
    (1, 'Ahmed Nabil',      'ahmed.nabil@brightpeak.edu',   'Data Science'),
    (2, 'Rana El-Masry',    'rana.elmasry@brightpeak.edu',  'Computer Science'),
    (3, 'Hesham Zaki',      'hesham.zaki@brightpeak.edu',   'Software Engineering'),
    (4, 'sara ahmed',      'sara.ahmed@brightpeak.edu',   'Artificial Intelligence'),
    (5, 'Omar Taha',        'omar.taha@brightpeak.edu',     'mobile development'),
    (6, 'mohamed khaled',      'mohamed.khaled@brightpeak.edu',   'Cloud & DevOps');
-- ------------------------------------------------------------
-- Students
-- ------------------------------------------------------------
INSERT INTO Students (student_id, name, email, level) VALUES
    (1,  'Ahmed Mostafa',   'ahmed.mostafa@student.brightpeak.edu',   'Beginner'),
    (2,  'Farida Ibrahim',  'farida.ibrahim@student.brightpeak.edu',  'Intermediate'),
    (3,  'Mariam Nabil',    'mariam.nabil@student.brightpeak.edu',    'Advanced'),
    (4,  'Hassan Ali',      'hassan.ali@student.brightpeak.edu',      'Beginner'),
    (5,  'Salma Mahmoud',   'salma.mahmoud@student.brightpeak.edu',   'Intermediate'),
    (6,  'Youssef Kamal',   'youssef.kamal@student.brightpeak.edu',   'Advanced'),
    (7,  'Nada Wael',       'nada.wael@student.brightpeak.edu',       'Beginner'),
    (8,  'Omar Sherif',     'omar.sherif@student.brightpeak.edu',     'Intermediate'),
    (9,  'Rana Adel',       'rana.adel@student.brightpeak.edu',       'Advanced'),
    (10, 'Khaled Fouad',    'khaled.fouad@student.brightpeak.edu',    'Beginner');
    

-- ------------------------------------------------------------
-- Courses
-- ------------------------------------------------------------
INSERT INTO Courses (course_id, title, category, duration, instructor_id) VALUES
    (1, 'Introduction to Python',        'Programming',     30, 1),
    (2, 'Data Structures & Algorithms',  'Programming',     45, 2),
    (3, 'Machine Learning Fundamentals', 'AI & Data',       50, 3),
    (4, 'Web Development with React',    'Web Development', 40, 4),
    (5, 'Database Design & SQL',         'Data',            35, 5),
    (6,  'Advanced Python & OOP',              'Programming',      35, 6),
    (7,  'Node.js & Backend Development',      'Web Development',  40, 7),
    (8,  'Cloud Computing Fundamentals',       'Cloud & DevOps',   30, 8),
    (9,  'Cybersecurity Essentials',           'Security',         35, 9),
    (10, 'Data Visualization with Python',     'AI & Data',        25, 3),
    (11, 'Mobile App Development with Flutter','Mobile Development',45, 10);
    

-- ------------------------------------------------------------
-- Enrollments
-- ------------------------------------------------------------
INSERT INTO Enrollments (enrollment_id, student_id, course_id, status, progress, enrollment_date) VALUES
    (1,  1,  1, 'active',    40,  '2026-05-01'),
    (2,  1,  4, 'active',    15,  '2026-06-10'),
    (3,  2,  1, 'completed', 100, '2026-03-01'),
    (4,  2,  2, 'active',    60,  '2026-05-15'),
    (5,  3,  3, 'active',    75,  '2026-04-20'),
    (6,  3,  5, 'completed', 100, '2026-02-10'),
    (7,  4,  1, 'dropped',   20,  '2026-04-01'),
    (8,  5,  2, 'active',    50,  '2026-05-20'),
    (9,  5,  4, 'active',    30,  '2026-06-01'),
    (10, 6,  3, 'completed', 100, '2026-01-15'),
    (11, 7,  1, 'active',    10,  '2026-07-01'),
    (12, 8,  5, 'active',    65,  '2026-05-05'),
    (13, 9,  3, 'active',    80,  '2026-04-25'),
    (14, 10, 2, 'active',    25,  '2026-06-15'),
    (15, 10, 4, 'active',    5,   '2026-07-10'),
    (16, 2,  6,  'active',    45,  '2026-06-05'),
    (17, 6,  6,  'completed', 100, '2026-03-20'),
    (18, 3,  7,  'active',    55,  '2026-06-12'),
    (19, 9,  7,  'active',    20,  '2026-07-05'),
    (20, 5,  8,  'active',    35,  '2026-06-18'),
    (21, 8,  8,  'active',    10,  '2026-07-15'),
    (22, 4,  9,  'active',    25,  '2026-06-22'),
    (23, 10, 9,  'active',    15,  '2026-07-20'),
    (24, 3,  10, 'completed', 100, '2026-02-15'),
    (25, 6,  10, 'active',    60,  '2026-05-25'),
    (26, 2,  11, 'active',    40,  '2026-06-30'),
    (27, 9,  11, 'active',    30,  '2026-07-08');

-- ------------------------------------------------------------
-- Assignments
-- ------------------------------------------------------------
INSERT INTO Assignments (assignment_id, course_id, title, deadline, max_score) VALUES
    (1, 1, 'Python Basics Quiz',            '2026-05-15', 100),
    (2, 1, 'Functions & Loops Project',     '2026-06-01', 100),
    (3, 2, 'Sorting Algorithms Assignment', '2026-06-10', 100),
    (4, 2, 'Binary Trees Lab',              '2026-06-25', 100),
    (5, 3, 'Linear Regression Exercise',    '2026-05-20', 100),
    (6, 3, 'Classification Project',        '2026-06-15', 100),
    (7, 4, 'React Components Task',         '2026-06-20', 100),
    (8, 5, 'SQL Queries Assignment',        '2026-04-01', 100),
    (9, 5, 'Database Schema Design',        '2026-04-20', 100),
    (10, 6,  'OOP Design Project',            '2026-07-01', 100),
    (11, 6,  'Decorators Exercise',           '2026-07-15', 100),
    (12, 7,  'Express API Assignment',        '2026-07-05', 100),
    (13, 7,  'REST API Project',              '2026-07-25', 100),
    (14, 8,  'AWS Deployment Lab',            '2026-07-10', 100),
    (15, 8,  'Cloud Architecture Quiz',       '2026-07-20', 100),
    (16, 9,  'Network Security Assessment',   '2026-07-12', 100),
    (17, 9,  'Attack Vector Analysis',        '2026-07-28', 100),
    (18, 10, 'Matplotlib Project',            '2026-06-01', 100),
    (19, 10, 'Dashboard Building Task',       '2026-06-20', 100),
    (20, 11, 'Flutter Widget Lab',            '2026-07-18', 100),
    (21, 11, 'State Management Project',      '2026-08-01', 100);
 

-- ------------------------------------------------------------
-- Grades
-- ------------------------------------------------------------
INSERT INTO Grades (grade_id, student_id, assignment_id, score, graded_by) VALUES
    (1,  1, 1, 85, 1),
    (2,  2, 1, 92, 1),
    (3,  2, 3, 78, 2),
    (4,  3, 5, 95, 3),
    (5,  3, 8, 88, 5),
    (6,  3, 9, 90, 5),
    (7,  5, 3, 70, 2),
    (8,  6, 5, 82, 3),
    (9,  6, 6, 91, 3),
    (10, 8, 8, 76, 5),
    (11, 9, 5, 89, 3),
    (12, 9, 6, 84, 3),
    (13, 2, 10, 88, 6),
    (14, 6, 11, 91, 6),
    (15, 3, 12, 79, 7),
    (16, 9, 13, 85, 7),
    (17, 5, 14, 82, 8),
    (18, 4, 16, 90, 9),
    (19, 3, 18, 94, 3),
    (20, 6, 19, 87, 3),
    (21, 2, 20, 80, 10);
 

-- ------------------------------------------------------------
-- Attendance
-- ------------------------------------------------------------
INSERT INTO Attendance (attendance_id, student_id, course_id, percentage) VALUES
    (1,  1,  1, 88.5),
    (2,  1,  4, 95.0),
    (3,  2,  1, 100.0),
    (4,  2,  2, 91.0),
    (5,  3,  3, 97.5),
    (6,  3,  5, 100.0),
    (7,  4,  1, 60.0),
    (8,  5,  2, 85.0),
    (9,  5,  4, 78.0),
    (10, 6,  3, 99.0),
    (11, 7,  1, 65.5),
    (12, 8,  5, 90.0),
    (13, 9,  3, 93.0),
    (14, 10, 2, 72.0),
    (15, 10, 4, 55.0),
    (16, 2,  6,  92.0),
    (17, 6,  6,  88.0),
    (18, 3,  7,  95.0),
    (19, 9,  7,  70.0),
    (20, 5,  8,  80.0),
    (21, 8,  8,  60.0),
    (22, 4,  9,  85.0),
    (23, 10, 9,  50.0),
    (24, 3,  10, 97.0),
    (25, 6,  10, 90.0),
    (26, 2,  11, 78.0),
    (27, 9,  11, 65.0);
 

-- ------------------------------------------------------------
-- Policies
-- ------------------------------------------------------------
INSERT INTO Policies (policy_id, title, category, content) VALUES
    (1, 'Attendance Policy',
        'Attendance',
        'Students must maintain at least 75% attendance per course to remain eligible for final assessments. Falling below this threshold may result in a warning or course suspension.'),
    (2, 'Scholarship Policy',
        'Financial Aid',
        'Students with an overall grade average above 90% across all completed courses are eligible to apply for a merit-based scholarship covering up to 50% of tuition fees.'),
    (3, 'Academic Integrity Rules',
        'Conduct',
        'Plagiarism, cheating, or unauthorized collaboration on assignments and exams is strictly prohibited and may result in a zero score or academic probation.'),
    (4, 'Late Submission Policy',
        'Assignments',
        'Assignments submitted after the deadline incur a 10% score deduction per day late, up to a maximum of 3 days, after which submissions are no longer accepted.'),
    (5, 'Course Withdrawal Policy',
        'Enrollment',
        'Students may withdraw from a course within the first two weeks of enrollment without academic penalty. Withdrawals after this period are recorded as "dropped".');


-- ------------------------------------------------------------
-- CourseMaterials

-- ------------------------------------------------------------
INSERT INTO CourseMaterials (material_id, course_id, title, description, material_type, source_file) VALUES
    (1, 1, 'Python Basics',            'Syntax, variables, and running your first Python program.', 'lecture', 'python/basics.md'),
    (2, 1, 'Variables and Data Types', 'Numbers, strings, booleans, and type conversion in Python.', 'lecture', 'python/variables.md'),
    (3, 1, 'Functions',                'Defining functions, parameters vs. arguments, return values.', 'lecture', 'python/functions.md'),

    (4, 2, 'Arrays',                   'Array structure, indexing, and common operations.',           'chapter', 'data_structures/arrays.md'),
    (5, 2, 'Linked Lists',             'Singly linked lists, traversal, insertion, and deletion.',     'chapter', 'data_structures/linked_lists.md'),
    (6, 2, 'Stacks',                   'LIFO structure, push/pop operations, and use cases.',          'chapter', 'data_structures/stacks.md'),

    (7, 3, 'Introduction to Machine Learning', 'What ML is, supervised vs. unsupervised learning.',    'lecture', 'machine_learning/introduction.md'),
    (8, 3, 'Linear Regression',        'Fitting a line to data and interpreting coefficients.',        'lecture', 'machine_learning/linear_regression.md'),
    (9, 3, 'Classification',           'Classification vs. regression, decision boundaries, accuracy.', 'lecture', 'machine_learning/classification.md'),

    (10, 4,  'React Components',              'Building blocks of a React app: functional components and JSX.', 'lecture', 'react/components.md'),
    (11, 4,  'State and Props',                'Managing component state and passing data via props.',           'lecture', 'react/state_props.md'),
    (12, 4,  'Hooks in React',                 'useState, useEffect, and building custom hooks.',                'lecture', 'react/hooks.md'),
 
    (13, 5,  'SQL Basics',                     'SELECT, WHERE, ORDER BY, and basic filtering.',                  'lecture', 'sql/basics.md'),
    (14, 5,  'Joins and Relationships',        'INNER, LEFT, and RIGHT joins across related tables.',            'lecture', 'sql/joins.md'),
    (15, 5,  'Database Schema Design',         'Normalization, keys, and designing a relational schema.',        'reading', 'sql/schema_design.md'),
 
    (16, 6,  'Object-Oriented Programming',    'Classes, objects, inheritance, and polymorphism in Python.',     'lecture', 'python_advanced/oop.md'),
    (17, 6,  'Decorators and Generators',      'Writing decorators and using generators for lazy evaluation.',   'lecture', 'python_advanced/decorators_generators.md'),
    (18, 6,  'Error Handling and Testing',     'Exceptions, try/except, and writing unit tests.',                'chapter', 'python_advanced/error_handling.md'),
 
    (19, 7,  'Introduction to Node.js',        'The Node.js runtime, modules, and the event loop.',              'lecture', 'nodejs/introduction.md'),
    (20, 7,  'Express.js Basics',              'Routing, middleware, and building a basic server with Express.', 'lecture', 'nodejs/express_basics.md'),
    (21, 7,  'Building REST APIs',             'Designing and implementing RESTful endpoints.',                  'exercise','nodejs/rest_apis.md'),
 
    (22, 8,  'Cloud Computing Basics',         'Core concepts: IaaS, PaaS, SaaS, and cloud providers.',          'lecture', 'cloud/basics.md'),
    (23, 8,  'AWS Fundamentals',               'Core AWS services: EC2, S3, and IAM.',                           'lecture', 'cloud/aws_fundamentals.md'),
    (24, 8,  'Deploying Applications to the Cloud', 'Hands-on deployment of a sample app to a cloud provider.',  'exercise','cloud/deployment.md'),
 
    (25, 9,  'Introduction to Cybersecurity',  'Core security concepts: confidentiality, integrity, availability.', 'lecture', 'cybersecurity/introduction.md'),
    (26, 9,  'Network Security Basics',        'Firewalls, VPNs, and securing network traffic.',                 'chapter', 'cybersecurity/network_security.md'),
    (27, 9,  'Common Attack Vectors',          'Phishing, malware, and social engineering overview.',            'reading', 'cybersecurity/attack_vectors.md'),
 
    (28, 10, 'Intro to Data Visualization',    'Why visualization matters and choosing the right chart type.',   'lecture', 'data_visualization/introduction.md'),
    (29, 10, 'Plotting with Matplotlib',       'Creating line, bar, and scatter plots with Matplotlib.',         'lecture', 'data_visualization/matplotlib.md'),
    (30, 10, 'Building Dashboards',            'Combining charts into an interactive dashboard.',                'exercise','data_visualization/dashboards.md'),
 
    (31, 11, 'Introduction to Flutter',        'Flutter architecture, widgets, and setting up a project.',       'lecture', 'flutter/introduction.md'),
    (32, 11, 'Widgets and Layouts',            'Stateless vs. stateful widgets and layout composition.',         'lecture', 'flutter/widgets_layouts.md'),
    (33, 11, 'State Management in Flutter',    'Managing app state with Provider or similar patterns.',          'chapter', 'flutter/state_management.md');
 