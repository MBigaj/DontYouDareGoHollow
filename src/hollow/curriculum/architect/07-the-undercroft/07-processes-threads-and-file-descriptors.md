# Processes, Threads and File Descriptors

> **Why this matters for you:** 'Too many open files' and zombie workers are Linux problems with Python symptoms.

## You should be able to
- Explain processes, threads, file descriptors and ulimits
- Explain epoll and why async servers scale
- Debug with ps, lsof, strace and /proc

## Exam questions
- What is a file descriptor, and what uses one?
- Why can one async process serve thousands of connections?
- A worker is stuck. How do you see what it is doing?
