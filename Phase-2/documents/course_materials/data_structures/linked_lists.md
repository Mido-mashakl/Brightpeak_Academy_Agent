
# Linked Lists
## Learning Objectives
By the end of this material, students should be able to:
- Explain the basic structure of a linked list.
- Distinguish between nodes and links.
- Describe the difference between singly and doubly linked lists.
- Traverse a linked list.
- Insert and remove nodes.
- Compare linked lists with Python lists.
## Introduction
A linked list is a linear data structure made up of a sequence of nodes. Unlike an array or Python list, the elements of a linked list are not required to be stored next to each other in memory.
Each node contains:
- Data stored by the node.
- A reference to another node.
In a singly linked list, each node points to the next node in the sequence.
A simple representation is:
```text
[Data | Next] -> [Data | Next] -> [Data | Next] -> None

The first node is called the head, and the final node points to None.

Nodes

A node is the basic building block of a linked list.

In Python, a node can be represented using a class:

class Node:
    def __init__(self, data):
        self.data = data
        self.next = None

The data attribute stores the value, while next stores a reference to the next node.

For example:

first = Node("Python")
second = Node("Data Structures")
first.next = second

The structure is now:

Python -> Data Structures -> None

Creating a Singly Linked List

A linked list can be created by connecting several nodes.

first = Node("Python")
second = Node("Data Structures")
third = Node("Algorithms")
first.next = second
second.next = third

The resulting structure is:

Python -> Data Structures -> Algorithms -> None

The first node acts as the head of the linked list.

Traversing a Linked List

Traversal means visiting each node in the linked list in sequence.

A pointer can be used to move from one node to the next:

current = first
while current is not None:
    print(current.data)
    current = current.next

The loop starts at the head and continues until current becomes None.

The output is:

Python
Data Structures
Algorithms

Searching for a Value

A linked list can be searched by traversing its nodes.

def contains(head, target):
    current = head
    while current is not None:
        if current.data == target:
            return True
        current = current.next
    return False

The function returns True if the target value is found and False otherwise.

For example:

contains(first, "Python")

returns True.

Inserting at the Beginning

Inserting a new node at the beginning of a singly linked list is efficient.

Suppose the current list is:

Python -> Data Structures -> None

A new node can be inserted before Python:

new_node = Node("Programming")
new_node.next = first
first = new_node

The resulting list is:

Programming -> Python -> Data Structures -> None

Only the new node and the head reference need to be updated.

Inserting at the End

To insert a node at the end of a singly linked list, the list must be traversed until the final node is reached.

new_node = Node("Algorithms")
current = first
while current.next is not None:
    current = current.next
current.next = new_node

The resulting list ends with the new node.

Programming -> Python -> Data Structures -> Algorithms -> None

If the list contains n nodes, finding the last node generally requires O(n) time when no tail reference is maintained.

Removing a Node

To remove a node from a singly linked list, the reference of the previous node must be updated.

Suppose the list is:

Python -> Data Structures -> Algorithms -> None

To remove Data Structures, the previous node should point directly to Algorithms.

Conceptually:

Python ----------------> Algorithms -> None

A possible implementation is:

def remove(head, target):
    if head is None:
        return None
    if head.data == target:
        return head.next
    current = head
    while current.next is not None:
        if current.next.data == target:
            current.next = current.next.next
            return head
        current = current.next
    return head

This implementation removes the first node whose data matches the target.

Singly Linked Lists

In a singly linked list, every node contains a reference to the next node only.

[Data | Next] -> [Data | Next] -> [Data | Next] -> None

The list can only be traversed in the forward direction.

Singly linked lists generally require less memory per node than doubly linked lists because each node stores only one link.

Doubly Linked Lists

A doubly linked list stores references to both the previous and next nodes.

None <- [Prev | Data | Next] <-> [Prev | Data | Next] -> None

A node can be represented as:

class DoublyNode:
    def __init__(self, data):
        self.data = data
        self.prev = None
        self.next = None

The additional prev reference allows traversal in both directions.

Comparing Linked Lists and Python Lists

Python’s built-in list is implemented as a dynamic array rather than a traditional linked list.

There are important differences between the two structures.

Operation	Python List	Singly Linked List
Access by index	O(1)	O(n)
Search	O(n)	O(n)
Insert at beginning	O(n)	O(1)
Remove from beginning	O(n)	O(1)
Append	O(1) amortized	O(n) without a tail reference
Memory per element	Lower overhead	Additional reference required

The best data structure depends on the operations that a program needs to perform frequently.

Advantages of Linked Lists

Linked lists can be useful when a program frequently inserts or removes elements from known positions.

Advantages include:

* Nodes can be added without shifting all later elements.
* The structure can grow dynamically.
* Insertion and removal can be efficient when the relevant node or position is already known.
* They provide a useful foundation for other data structures such as queues and some graph representations.

Limitations of Linked Lists

Linked lists also have disadvantages.

Common limitations include:

* No constant-time random access by index.
* Additional memory is required for node references.
* Traversal is generally sequential.
* Accessing an element near the end requires following the links from the beginning unless additional references are maintained.

For many everyday Python programs, the built-in list is more convenient and often more efficient.

Time Complexity

For a singly linked list with n nodes:

* Accessing a node by position: O(n)
* Searching for a value: O(n)
* Inserting at the head: O(1)
* Removing the head: O(1)
* Inserting at the end: O(n) without a tail reference
* Searching for and removing a value: O(n)

The exact complexity of an operation can depend on what references are already available.

For example, inserting a node after a known node can be performed in O(1) time because no traversal is required.

Common Errors

A common mistake is forgetting to update the next reference when inserting a node.

For example:

new_node = Node("Python")
first = new_node

This replaces the head but does not connect the new node to the existing list.

The correct approach is:

new_node.next = first
first = new_node

Another common error is traversing a list without moving to the next node:

current = first
while current is not None:
    print(current.data)

This creates an infinite loop because current never changes.

The traversal should update the reference:

current = first
while current is not None:
    print(current.data)
    current = current.next

Summary

A linked list is a linear data structure consisting of nodes connected through references.

In a singly linked list, each node stores data and a reference to the next node. The first node is the head, and the final node points to None.

Linked lists provide efficient insertion and removal in certain situations, but they do not provide constant-time random access like Python lists.

Understanding linked lists is important for studying data structures, algorithm complexity, queues, stacks, and other linked data structures.