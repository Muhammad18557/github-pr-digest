import os
import requests
import openai
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from flask import (
    Flask,
    request,
    render_template,
    session,
    redirect,
    url_for,
    jsonify,
    send_file,
)
from flask_session import Session
from datetime import datetime
from io import BytesIO

app = Flask(__name__)

# Generate a persistent secret key if it doesn't exist
secret_key_file = ".flask_secret_key"
if os.path.exists(secret_key_file):
    with open(secret_key_file, 'rb') as f:
        app.secret_key = f.read()
else:
    # Generate a new secret key
    app.secret_key = os.urandom(24)
    with open(secret_key_file, 'wb') as f:
        f.write(app.secret_key)

# Configure session to be more persistent
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60  # 1 hour
app.config['SESSION_FILE_THRESHOLD'] = 100  # Maximum number of sessions to store

# Initialize Flask-Session
Session(app)

from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY


@app.route("/orgs", methods=["GET"])
def get_user_orgs():
    """Fetch all organizations that the user has access to"""
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        response = requests.get("https://api.github.com/user/orgs", headers=headers)
        response.raise_for_status()
        orgs = [org['login'] for org in response.json()]
        return jsonify({"organizations": orgs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def index():
    """Renders the main page with organization selection"""
    return render_template("index.html")


@app.route("/get_repos", methods=["POST"])
def get_repos():
    """
    AJAX endpoint: receives { "org": "<orgName>" }
    and returns a JSON list of that org's repos (full_name).
    """
    data = request.json
    org_name = data.get("org")
    if not org_name:
        return jsonify({"error": "No organization provided."}), 400

    repos = fetch_org_repos(org_name)
    return jsonify({"repos": repos})


@app.route("/start-summary", methods=["POST"])
def start_summary():
    """
    Receives the form:
      - org name
      - list of selected repos
      - start_date, end_date
    Immediately shows a loading page, then calls /summaries
    to do the actual summarization.
    """
    org_name = request.form.get("org_name")
    selected_repos = request.form.getlist("repos")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")

    session["org_name"] = org_name
    session["selected_repos"] = selected_repos
    session["start_date"] = start_date
    session["end_date"] = end_date

    # Render the loading page, which will redirect to /summaries
    return render_template("loading.html")


@app.route("/summaries", methods=["GET"])
def summaries():
    """
    1. Fetch and summarize merged PRs for the chosen repos & date range (chunked).
    2. Store final results in session for PDF generation.
    3. Render the results page with 'Download PDF' button.
    """
    org_name = session.get("org_name")
    selected_repos = session.get("selected_repos", [])
    start_date = session.get("start_date")
    end_date = session.get("end_date")

    if not (org_name and selected_repos and start_date and end_date):
        return redirect(url_for("index"))

    repo_pr_data = {}
    # For each selected repo (full_name), fetch merged PRs
    for full_name in selected_repos:
        try:
            owner, repo = full_name.split("/")
        except ValueError:
            continue

        prs = fetch_merged_prs(owner, repo, start_date, end_date)
        repo_pr_data[full_name] = prs

    # Summarize each repo
    repo_summaries = {}
    pr_level_summaries = {}
    for repo_identifier, pr_list in repo_pr_data.items():
        final_summary, pr_summaries = chunked_summarize_repo(repo_identifier, pr_list)
        repo_summaries[repo_identifier] = final_summary
        pr_level_summaries[repo_identifier] = pr_summaries

    # Store results in session so we can generate PDF and make the session permanent
    session.permanent = True
    session["repo_pr_data"] = repo_pr_data
    session["repo_summaries"] = repo_summaries
    session["pr_level_summaries"] = pr_level_summaries

    return render_template(
        "results.html",
        org_name=org_name,
        start_date=start_date,
        end_date=end_date,
        repo_summaries=repo_summaries,
        repo_pr_data=repo_pr_data,
        pr_level_summaries=pr_level_summaries,
    )


@app.route("/download_pdf")
def download_pdf():
    """
    Generate a PDF from the stored summary data using pdfkit and serve it.
    """
    repo_summaries = session.get("repo_summaries")
    repo_pr_data = session.get("repo_pr_data")
    pr_level_summaries = session.get("pr_level_summaries", {})
    start_date = session.get("start_date")
    end_date = session.get("end_date")
    org_name = session.get("org_name")

    if not (repo_summaries and repo_pr_data and start_date and end_date and org_name):
        return redirect(url_for("index"))

    # Create PDF using reportlab
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30
    )
    heading2_style = ParagraphStyle(
        'Heading2',
        parent=styles['Heading2'],
        fontSize=18,
        spaceAfter=12
    )
    normal_style = styles['Normal']
    
    # Build the PDF content
    elements = []
    
    # Add title
    elements.append(Paragraph(f"Summary for {org_name} ({start_date} - {end_date})", title_style))
    elements.append(Spacer(1, 12))
    
    # Add repository summaries
    for repo, summary in repo_summaries.items():
        elements.append(Paragraph(repo, heading2_style))
        elements.append(Paragraph(f"<b>Final Summary:</b><br/>{summary}", normal_style))
        elements.append(Spacer(1, 12))
        
        elements.append(Paragraph("<b>Pull Requests:</b>", heading2_style))
        
        for pr in repo_pr_data[repo]:
            # Add PR title and metadata
            elements.append(Paragraph(
                f"<b>PR #{pr['number']}: {pr['title']}</b><br/>"
                f"<b>Merged At:</b> {pr['merged_at']}<br/>"
                f"<b>Author:</b> {pr['author']}",
                normal_style
            ))
            
            # Add PR summary if available
            if pr_level_summaries.get(repo) and pr_level_summaries[repo].get(pr['number']):
                elements.append(Spacer(1, 6))
                elements.append(Paragraph(
                    f"<b>Summary:</b><br/>{pr_level_summaries[repo][pr['number']]}",
                    normal_style
                ))
            
            # Add commits
            if pr['commits']:
                elements.append(Paragraph("<b>Commits:</b>", normal_style))
                commit_text = "<br/>".join([f"• {c['author']}: {c['message']}" for c in pr['commits']])
                elements.append(Paragraph(commit_text, normal_style))
            
            # Add files
            if pr['files']:
                elements.append(Paragraph("<b>Files Changed:</b>", normal_style))
                files_text = "<br/>".join([f"• {f['filename']} ({f['changes']} changes)" for f in pr['files']])
                elements.append(Paragraph(files_text, normal_style))
            
            elements.append(Spacer(1, 12))
    
    # Build the PDF
    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()

    # Return the PDF as a file download
    filename = f"summary_{org_name}_{start_date}_to_{end_date}.pdf"
    return send_file(
        BytesIO(pdf_data),
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )


def fetch_org_repos(org_name):
    """
    Fetch all repos (public/private) in this org that the user can access.
    Returns a list of "full_name" (e.g. "defog-ai/defog-self-hosted").
    """
    url = f"https://api.github.com/orgs/{org_name}/repos"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    params = {"per_page": 100, "sort": "updated"}
    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        return []
    data = r.json()
    return [repo["full_name"] for repo in data]


def fetch_merged_prs(owner, repo, start_date, end_date):
    """
    Fetch merged PRs within the date range (YYYY-MM-DD).
    Returns a list of PR data with commits and file info.
    """
    base_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    all_prs = []
    page = 1
    while True:
        params = {
            "state": "closed",
            "sort": "updated",
            "direction": "desc",
            "per_page": 50,
            "page": page,
        }
        resp = requests.get(base_url, headers=headers, params=params)
        if resp.status_code == 404:
            print(f"Repo not found or no access: {owner}/{repo}")
            return []
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        all_prs.extend(data)
        page += 1

    # Filter to merged PRs within the date range
    filtered_prs = []
    for pr in all_prs:
        merged_at = pr.get("merged_at")
        # merged_at like '2025-02-19T13:00:00Z'
        # Compare only the date part: merged_at[:10] => '2025-02-19'
        if merged_at and (start_date <= merged_at[:10] <= end_date):
            pr_number = pr["number"]
            commits = fetch_pr_commits(pr["commits_url"])
            files = fetch_pr_files(owner, repo, pr_number)
            filtered_prs.append(
                {
                    "number": pr_number,
                    "title": pr["title"],
                    "merged_at": pr["merged_at"],
                    "author": pr["user"]["login"],
                    "commits": commits,
                    "files": files,
                }
            )
    return filtered_prs


def fetch_pr_commits(commits_url):
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    r = requests.get(commits_url, headers=headers)
    r.raise_for_status()
    data = r.json()
    commits = []
    for c in data:
        message = c["commit"]["message"]
        author = c["commit"]["author"]["name"]
        commits.append({"message": message, "author": author})
    return commits


def fetch_pr_files(owner, repo, pr_number):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    data = r.json()
    files_info = []
    for f in data:
        files_info.append(
            {
                "filename": f["filename"],
                "changes": f.get("changes"),
                "status": f.get("status"),
            }
        )
    return files_info


def chunked_summarize_repo(repo_identifier, pr_list):
    """
    Summarize each PR individually (small GPT calls), then combine.
    Returns a tuple of (final_summary, pr_summaries) where pr_summaries is a dict
    mapping PR numbers to their individual summaries.
    """
    if not pr_list:
        return (f"No merged PRs found for {repo_identifier} in this date range.", {})

    partial_summaries = []
    pr_summaries = {}
    for pr in pr_list:
        summary = summarize_single_pr(repo_identifier, pr)
        partial_summaries.append(summary)
        pr_summaries[pr['number']] = summary

    # Summarize the partial summaries
    final_summary = summarize_partial_summaries(repo_identifier, partial_summaries)
    return (final_summary, pr_summaries)


def summarize_single_pr(repo_identifier, pr):
    """
    Summarize a single PR. This ensures we don't exceed GPT tokens.
    """
    pr_header = (
        f"Repository: {repo_identifier}\n"
        f"PR #{pr['number']}: {pr['title']} (merged {pr['merged_at']} by {pr['author']})\n"
    )

    commit_lines = [f"- {c['message']} (by {c['author']})" for c in pr["commits"]]
    file_lines = [
        f"- {f['filename']} [{f['status']}, {f.get('changes', 'N/A')} changes]"
        for f in pr["files"]
    ]

    prompt = (
        "You are an AI assistant that summarizes a single pull request.\n\n"
        f"{pr_header}\n"
        f"Commits:\n" + "\n".join(commit_lines) + "\n\n"
        "Files Changed:\n" + "\n".join(file_lines) + "\n\n"
        "Provide a concise (2-4 sentences) summary of what changed and why."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a software engineering summarizer.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1000,
            temperature=0,
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Error summarizing PR #{pr['number']}: {e}"


def summarize_partial_summaries(repo_identifier, partial_summaries):
    """
    Combine multiple short PR summaries into a final repository summary.
    """
    if len(partial_summaries) == 1:
        return partial_summaries[0]

    combined_text = "\n".join(
        [
            f"PR Summary {i+1}:\n{summary}\n"
            for i, summary in enumerate(partial_summaries)
        ]
    )

    prompt = (
        f"You are an AI that creates an overall summary for {repo_identifier}.\n\n"
        f"The following are partial summaries of multiple pull requests:\n\n"
        f"{combined_text}\n\n"
        "Please combine them into a concise overall summary (5-6 sentences max)."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert summarizer."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.7,
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Error generating final summary: {e}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
