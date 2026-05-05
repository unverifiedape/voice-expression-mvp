# GitHub download ready package

This package is prepared for a GitHub-based update flow.

## Files
- `static/index.html`

## Push to GitHub
```bash
git add static/index.html
git commit -m "ui: real designed interactive layout"
git push --force
```

## Update AWS
```bash
cd /opt/voice-expression-mvp
git fetch origin
git reset --hard origin/main
sudo systemctl restart voice-expression
sudo systemctl restart nginx
```

## Future ZIP download
After you push this to GitHub:
- open your repo
- click **Code**
- click **Download ZIP**
