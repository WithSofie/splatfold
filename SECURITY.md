# Security policy

## Supported versions

Security fixes are made on the current Splatfold release line and the `main`
branch. The historical Obtuse prototype and copied `preprocessor.py` scripts
are unsupported; reproduce reports against the current Splatfold version
before filing them.

## Trust model

Splatfold treats project source as input data while building: it reads files,
tokenizes them, parses their ASTs, renders source, and compile-checks the result.
It does not import or execute project modules during this process.

This does not make generated programs safe to execute. Running a generated
file executes the included project code with the caller's normal Python
permissions.

Local wildcard imports may intentionally resolve through configured roots,
search paths, and relative parent packages. Callers processing untrusted source
trees should therefore control those paths and inspect the dependency list
before using or executing an artifact.

Security reports should use the repository's private security-advisory channel
once the Splatfold repository is published. Do not disclose a suspected
vulnerability in a public issue before a private report has been assessed.
