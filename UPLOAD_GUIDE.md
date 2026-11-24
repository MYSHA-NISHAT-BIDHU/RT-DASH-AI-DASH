# Publish the reviewed code in the existing GitHub repository

Destination: https://github.com/MYSHA-NISHAT-BIDHU/RT-DASH-AI-DASH

**Before publishing:** Check the release folder one final time for files that your co-authors or institution require you to keep private. This release excludes dataset snapshots and manuscript drafts.

## Recommended: GitHub Desktop

1. Clone the existing **private** `RT-DASH-AI-DASH` repository in GitHub Desktop.
2. Extract the supplied ZIP. Copy the extracted files and folders into the root of the cloned repository, replacing the existing placeholder `README.md`, `rt_dash/README.md`, and `ai_dash/README.md` when prompted.
3. Verify that `rt_dash/research/` and `ai_dash/research/` contain `.py` files and that GitHub Desktop displays the expected additions. Commit as `Add reviewed RT-DASH and AI-DASH source release` and push to `main`.
4. Open GitHub repository Settings > General > Danger Zone > Change repository visibility > Make public. GitHub may ask you to confirm the repository name and reauthenticate.
5. Check the public repository's README and the two project directories in an incognito window.

## Alternative: Git command line

Clone the existing repository, copy this release's contents into its root, then run:

```bash
git add .
git commit -m "Add reviewed RT-DASH and AI-DASH source release"
git push origin main
```

Then change repository visibility in GitHub web Settings as above.

**Do not upload the ZIP as a single GitHub code file:** GitHub will not automatically unpack it into source directories.
