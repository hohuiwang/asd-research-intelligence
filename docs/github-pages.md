# Publish With GitHub Pages

This project exports a static website to `site/index.html`. GitHub Pages can publish that folder with the included workflow at `.github/workflows/pages.yml`.
The workflow now regenerates the ASD digest before every deployment and also runs on a weekly schedule.

## One-Time Setup

1. Create a new GitHub repository.
2. Create a GitHub personal access token for the push. If using **Tokens (classic)**, select both `repo` and `workflow`, because this repository includes `.github/workflows/pages.yml`.
3. In this folder, initialize Git and push to GitHub:

```bash
git init
git add .
git commit -m "Initial ASD research website"
git branch -M main
git remote add origin https://github.com/YOUR-USER/YOUR-REPO.git
git push -u origin main
```

3. In GitHub, open the repository settings.
4. Go to **Pages**.
5. Under **Build and deployment**, choose **GitHub Actions**.
6. Add a repository secret named `PUBMED_CONTACT_EMAIL` with a real contact email for NCBI PubMed requests.
7. Open the **Actions** tab and wait for **Deploy Website To GitHub Pages** to finish.

GitHub will show the public site URL on the workflow run and in **Settings > Pages**.

## Updating The Site

Run a fresh screen locally:

```bash
python3 -m research_agent.cli run-weekly --days 14 --max-results 50 --journal-scope high-impact --population-scope priority
```

Then commit and push the updated static site:

```bash
git add site/index.html site/.nojekyll
git commit -m "Update ASD research digest"
git push
```

The GitHub Pages workflow will regenerate the screen and redeploy automatically after the push.

## Automatic Refresh Schedule

The workflow also runs every Monday at 14:00 UTC.
That means the published site can refresh even if nobody manually runs the agent or pushes a new commit that week.

## Privacy Note

The public website is the generated `site/` folder. The local SQLite database and Markdown report are ignored by `.gitignore` by default.
