#!/bin/bash

# Navigate to your project directory
cd "C:/Users/User/Documents/FYP-IoT-Anomaly-Detection"

# Initialize Git if not already done
if [ ! -d ".git" ]; then
  git init
  git remote add origin https://github.com/ibrahimm2106/FYP-IoT-Anomaly-Detection.git
  git branch -M main
fi

# Stage and commit each file separately
for file in $(git ls-files --others --exclude-standard); do
  echo "Staging file: $file"
  git add "$file"
  echo "Committing file: $file"
  git commit -m "Added $file"
done

# Push all commits to the remote repository
echo "Pushing changes..."
git push -u origin main --force
echo "Done!"
