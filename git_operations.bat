@echo off
echo Starting git operations...

echo.
echo === Checking current status ===
git status

echo.
echo === Adding all changes ===
git add -A

echo.
echo === Checking status after add ===
git status

echo.
echo === Committing any changes on current branch ===
git commit -m "fix: Final cleanup and syntax fixes" || echo "No changes to commit"

echo.
echo === Switching to main branch ===
git checkout main

echo.
echo === Checking main branch status ===
git status

echo.
echo === Adding and committing any changes on main ===
git add -A
git commit -m "fix: Commit any remaining changes on main" || echo "No changes to commit on main"

echo.
echo === Switching back to working_auth ===
git checkout working_auth

echo.
echo === Merging working_auth into main ===
git checkout main
git merge working_auth

echo.
echo === Pushing changes to GitHub ===
git push origin main

echo.
echo === Making working_auth the default branch (setting HEAD) ===
git symbolic-ref HEAD refs/heads/working_auth
git push origin working_auth

echo.
echo === Final status ===
git status

echo.
echo Git operations completed!
pause 