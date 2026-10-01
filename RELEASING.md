# Release process

Splatfold publishes through GitHub Actions and PyPI Trusted Publishing. No
long-lived PyPI API token should be stored in the repository.

## Release checklist

1. Confirm that the intended PyPI version is not already published.
2. Update `VERSION` in `splatfold.py` and move the relevant changelog entries
   out of `Unreleased`.
3. Run the complete local checks documented in `CONTRIBUTING.md`.
4. Build both distributions with `python -m build` and verify them with
   `python -m twine check dist/*` and `check-wheel-contents dist/*.whl`.
5. Install the wheel in a new virtual environment outside the checkout.
6. Use that installed `splatfold` command to check, build, and execute the
   Acute integration example.
7. Merge the exact reviewed commit, create a signed `v<VERSION>` tag such as
   `v0.2.0`, and publish a GitHub Release. The workflow rejects any tag that
   does not exactly match `splatfold.VERSION`.
8. Let `.github/workflows/publish.yml` build fresh artifacts and publish them
   through the protected `pypi` environment.
9. Verify the PyPI page, installation command, package hashes, CLI version, and
   imported `splatfold.__version__` from a new environment.

Publishing is intentionally release-triggered. A successful local build or CI
run must never upload a distribution by itself.

Before the first release, configure a PyPI pending trusted publisher (or a
trusted publisher on an already-created project) using the final GitHub owner
and repository name, workflow filename `publish.yml`, and environment `pypi`.
Protect that GitHub environment with the repository's release approval policy.
