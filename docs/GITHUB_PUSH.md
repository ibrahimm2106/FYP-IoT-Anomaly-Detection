# Finish pushing to GitHub

The repo is cleaned for Git (no `.venv/`, no `__pycache__/`, no stray temp files). The first commit is on branch `main`. You only need to **authenticate once**, then run `git push`.

## Option A — HTTPS + Personal Access Token (often easiest on Windows)

1. GitHub → **Settings → Developer settings → Personal access tokens** → create a token with **`repo`** scope.
2. In the project folder:

   ```powershell
   git remote set-url origin https://github.com/ibrahimm2106/iot-autoencoder-artifact.git
   git push -u origin main
   ```

3. When prompted for password, paste the **token** (not your GitHub account password).

Or use **Git Credential Manager** / `gh auth login` so you are not prompted every time.

## Option B — SSH (matches `git@github.com:...`)

1. Ensure your public key is added: GitHub → **Settings → SSH and GPG keys** → paste contents of `%USERPROFILE%\.ssh\id_ed25519.pub` (or `id_rsa.pub`).
2. `%USERPROFILE%\.ssh\known_hosts` should contain GitHub’s host keys (see [GitHub SSH key fingerprints](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints)).
3. Test:

   ```powershell
   ssh -T git@github.com
   ```

4. Push:

   ```powershell
   git remote set-url origin git@github.com:ibrahimm2106/iot-autoencoder-artifact.git
   git push -u origin main
   ```

## After a successful push

Open `https://github.com/ibrahimm2106/iot-autoencoder-artifact` — you should see the files on `main`.

## Note on large files

This commit includes `models/` (e.g. `.keras`, `.pkl`) and `data/`. If GitHub rejects a file for size, use [Git LFS](https://git-lfs.com/) or move binaries to a release / external storage and document paths in `README.md`.
