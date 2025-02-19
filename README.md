# GitHub PR Summary Generator

A simple but useful tool that generates concise summaries of Pull Requests across your GitHub repositories. Built with Flask and OpenAI, this application helps teams quickly understand what has changed across their codebase over any time period.

![PR Summary Generator](https://raw.githubusercontent.com/your-username/what-has-changed/main/screenshots/demo.png)

## Features

- 🔍 **Smart PR Analysis**: Analyzes Pull Requests and generates human-readable summaries
- 📊 **Multi-Repository Support**: Select multiple repositories from your organizations
- 📅 **Flexible Date Range**: Choose any time period to analyze changes
- 📱 **Responsive UI**: Clean, simple interface that works on all devices
- 📄 **PDF Export**: Download summaries and raw PR data as PDF reports
- 🔒 **Secure**: Uses GitHub token for authentication and respects repository permissions

## Getting Started

### Prerequisites

- Python 3.8 or higher
- GitHub Personal Access Token (instructions below)
- OpenAI API Key

### Setting up GitHub Token

1. Go to GitHub.com → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a descriptive name (e.g., "PR Summary Generator")
4. Set expiration as needed
5. Select the following scopes:
   - `repo` (Full control of private repositories)
   - This gives access to read your repositories and pull requests
6. Click "Generate token"
7. **Important**: Copy the token immediately and store it securely. You won't be able to see it again!

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Muhammad18557/github-pr-digest.git
   cd github-pr-digest
   ```

2. (Optional) Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.template .env
   ```
   Edit `.env` and add your:
   - `GITHUB_TOKEN`
   - `OPENAI_API_KEY`

### Running the Application

1. Start the Flask server:
   ```bash
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5001
   ```

## Usage

1. Select your GitHub organization from the dropdown
2. Choose the repositories you want to analyze
3. Set the date range for PR analysis
4. Click "Fetch & Summarize"
5. View the generated summaries
6. Download the PDF report if needed

## Configuration

The application can be configured through environment variables:

- `GITHUB_TOKEN`: Your GitHub Personal Access Token
- `OPENAI_API_KEY`: Your OpenAI API Key
- `FLASK_ENV`: Set to `development` for debug mode
- `PORT`: Custom port (default: 5001)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with Flask and OpenAI
- Uses Bootstrap for UI components
- PDF generation powered by ReportLab
