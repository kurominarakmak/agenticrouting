# Explorer acceptance fixture

This preserves the disposable Explorer specification and buggy starter implementation used for the independent acceptance run. `SPEC.md` is copied verbatim; its SHA-256 is `c9390d7d34abe9b177df4ea6800645f40c0cef4bde9caf5f995a2384503b2aa6`. The original `verify_explorer.py` fails against the buggy starter, as expected.

`accepted-native-baseline.patch` is the preserved patch from the separate fixed-native Luna Medium baseline. Run `python3 reproduce_acceptance.py` from this directory to apply it to a temporary copy and run the independent six-case verifier. The replay does not invoke a model or modify the fixture.
