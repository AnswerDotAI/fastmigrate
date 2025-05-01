# Log FastMigrate work

Notes on the dev experience so far:

- AI asked for questions, and I provided answers
- AI generated a lot of code, which seemed correct, but worked less incrementally than would be preferable.
- AI got confused by setup.py vs pyproject.toml, and needed a few iterations to resolve that.

- Benefited from prompting regarding more test cases
- GOt list of suggestions
- Benefited from prompting regarding rollback. would have tried overly complex strategy
- Needed some help with git rebase



thoughts:
- tests pass. but who tests the tests?

cheap worker / expensive verifier


## Notes on work to do, as of commit b1b061d

### Reorganizing existing test data into a named 'test suite'

These files should be regarded as part of data supporting a test suite, rather than prat of the library:

- `.fastmigrate`
- `migrations/*`

So these files should be reorganized into a directory dedicated to one test suite. So let us call this `testsuite_a`, put it in a directory `testsuite_a`, under a directory `testsuites`. And test code should be rewritten so that tests which rely on that data refer to that test suite. 

The benefot of this is it would allow other independent test suites, and keep separate items organized.

### Create a new test suite that tests failures.

In addition to the existing test suite, there should be a new test suite that verifies that the library properly quits with a nonzero exit code when any of the migration scripts exits with a nonzero exit code.

### Use sqlite primitives to enforce db version table

Right now, there is a lot of code which handles the db version value, and ensures there is only one row.

Does sqlite have primitives which can enforce that invariant automatically and reduce the amount of code needed.



## Improvements to consider after 2380fe0

- [x]  add rollback for failed migrations
- [x]  add interactive mode
- [x]  add dry-run mode
- [x]  add better logging

## Improvements to consider after 6d0c48e

For the CLI we moved from a single function approach with a lot of parameters setting behaviors to a multi-function approach where each function represents a behavior. This makes the code more readable and easier to maintain, and ensures that if a behavior fails that another behavior is never run by accident.

We also moved from using Typer to a call_parse-based approach. This brings us into alignment with the rest of Answer.ai.