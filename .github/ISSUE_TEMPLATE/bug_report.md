---
name: Bug report
about: Something is broken or wrong
title: "[bug] "
labels: bug
---

**What's wrong**
One sentence.

**Repro**
The minimal command or code that surfaces the problem.

```
python smoke_test.py
# or
python -c "from aegis.pipeline import run_company_analysis; ..."
```

**What I expected**
What the output should be.

**What I got**
The actual output, error message, or traceback. Include the full
traceback if possible.

**Environment**
- Python version:
- OS:
- Installed via: `pip install` / clone / docker
- `pip list` output for the affected deps (pandas, numpy, networkx, etc.)
