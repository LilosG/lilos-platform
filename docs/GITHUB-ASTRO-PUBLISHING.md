# GitHub and Astro Publishing Adapter

Repository credentials are opaque Phase 7 secret references. Targets pin repository ID, base branch, and an allowed content path prefix. Paths are relative, traversal-free, content-extension allowlisted, and cannot target `.git`, `.github`, dependencies, or governing project files. Workers create a controlled branch from a recorded base commit, write only approved target files, create one idempotent pull request, and run configured Astro checks/build/tests. No force-push or automatic merge is authorized.
