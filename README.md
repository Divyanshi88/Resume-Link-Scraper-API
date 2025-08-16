# Resume Link Scraper API

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A powerful REST API that extracts hyperlinks from PDF resumes and scrapes content from linked webpages. Built with FastAPI and async processing for high performance.

## 🚀 Features

- **PDF Link Extraction**: Extract all visible and embedded URLs from PDF documents
- **Concurrent Web Scraping**: Asynchronous content retrieval with configurable limits
- **Intelligent Content Extraction**: Uses trafilatura with readability-lxml fallback
- **Robust Error Handling**: Graceful handling of corrupted PDFs and unreachable URLs
- **Structured JSON Response**: Detailed status and content for each processed URL
- **Health Monitoring**: Built-in health check endpoint
- **Highly Configurable**: Environment-based configuration for all parameters

## 📋 Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [API Documentation](#api-documentation)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Error Handling](#error-handling)
- [Contributing](#contributing)
- [License](#license)

## 🛠 Installation

### Prerequisites

- Python 3.9 or higher
- pip package manager

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/resume-link-scraper.git
   cd resume-link-scraper
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Required Dependencies

```
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
pymupdf>=1.23.0
httpx[http2]>=0.24.0
trafilatura>=1.6.0
readability-lxml>=0.8.0
python-multipart>=0.0.6
```

## ⚡ Quick Start

1. **Start the server**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Test the API**
   ```bash
   curl -X POST -F "resume_pdf=@path/to/your/resume.pdf" \
        http://localhost:8000/scrape-resume-links
   ```

3. **Access interactive docs**
   Open your browser to `http://localhost:8000/docs`

## 📚 API Documentation

### Endpoints

#### `POST /scrape-resume-links`

Extracts links from PDF and scrapes content from each URL.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Form field: `resume_pdf` (PDF file)

**Response:**
```json
{
  "scraped_data": [
    {
      "source_url": "https://github.com/username",
      "status": "success",
      "scraped_text": "GitHub profile content...",
      "error_message": null
    },
    {
      "source_url": "https://linkedin.com/in/username",
      "status": "error",
      "scraped_text": null,
      "error_message": "HTTP 999: LinkedIn access denied"
    }
  ]
}
```

#### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-08-16T12:00:00Z"
}
```

### Status Codes

| Code | Description |
|------|-------------|
| 200  | Success - PDF processed and links scraped |
| 400  | Bad Request - Invalid or corrupted PDF |
| 422  | Unprocessable Entity - No links found in PDF |
| 500  | Internal Server Error |

## ⚙️ Configuration

Configure the API using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRAPER_USER_AGENT` | Custom string | HTTP User-Agent header |
| `SCRAPER_TIMEOUT` | `12.0` | HTTP request timeout (seconds) |
| `SCRAPER_CONNECT_TIMEOUT` | `5.0` | Connection timeout (seconds) |
| `SCRAPER_MAX_CONCURRENCY` | `6` | Max concurrent connections |
| `SCRAPER_DELAY` | `0.15` | Delay between requests (seconds) |
| `SCRAPER_MAX_URLS` | `40` | Max URLs per PDF |
| `SCRAPER_MAX_PDF_MB` | `10` | Max PDF size (MB) |

### Example Configuration

Create a `.env` file:
```env
SCRAPER_USER_AGENT=ResumeScraperBot/1.0
SCRAPER_TIMEOUT=15.0
SCRAPER_MAX_CONCURRENCY=8
SCRAPER_DELAY=0.2
```

Or set environment variables:
```bash
export SCRAPER_TIMEOUT=15.0
export SCRAPER_MAX_CONCURRENCY=8
```

## 📖 Usage Examples

### cURL
```bash
# Basic usage
curl -X POST -F "resume_pdf=@resume.pdf" \
     http://localhost:8000/scrape-resume-links

# Save response to file
curl -X POST -F "resume_pdf=@resume.pdf" \
     http://localhost:8000/scrape-resume-links \
     -o scraping_results.json
```

### Python
```python
import requests
import json

# Upload and process PDF
with open('resume.pdf', 'rb') as f:
    files = {'resume_pdf': f}
    response = requests.post(
        'http://localhost:8000/scrape-resume-links',
        files=files
    )

# Process results
if response.status_code == 200:
    data = response.json()
    for item in data['scraped_data']:
        print(f"✓ {item['source_url']}: {item['status']}")
        if item['status'] == 'success':
            print(f"  Content: {item['scraped_text'][:100]}...")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

### JavaScript/Node.js
```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

async function scrapeResumeLinks() {
    const form = new FormData();
    form.append('resume_pdf', fs.createReadStream('resume.pdf'));
    
    try {
        const response = await axios.post(
            'http://localhost:8000/scrape-resume-links',
            form,
            { headers: form.getHeaders() }
        );
        
        console.log('Scraping results:', response.data);
    } catch (error) {
        console.error('Error:', error.response?.data || error.message);
    }
}

scrapeResumeLinks();
```

## 🚨 Error Handling

The API provides comprehensive error handling:

### PDF Processing Errors
- **Corrupted PDF**: Returns 400 with error details
- **No links found**: Returns 422 when PDF has no extractable URLs
- **File too large**: Rejects files exceeding size limit

### Web Scraping Errors
Per-URL errors are captured in the response:
- **HTTP 404/403/999**: Access denied or page not found
- **Connection timeout**: Network issues
- **SSL errors**: Certificate problems
- **Content extraction failure**: Unable to parse content

### Example Error Response
```json
{
  "scraped_data": [
    {
      "source_url": "https://private-site.com",
      "status": "error",
      "scraped_text": null,
      "error_message": "HTTP 403: Forbidden - Access denied"
    }
  ]
}
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   PDF Upload    │───▶│  Link Extraction │───▶│  Async Scraping │
│                 │    │   (PyMuPDF)      │    │   (httpx)       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐    ┌──────────────────┐            ▼
│ JSON Response   │◀───│ Content Extract. │    ┌─────────────────┐
│                 │    │ (trafilatura)    │    │  Rate Limiting  │
└─────────────────┘    └──────────────────┘    │  & Concurrency  │
                                               └─────────────────┘
```

## 🔧 Development

### Running in Development Mode
```bash
# Start with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/

# Format code
black .
isort .
```

### Docker Support
```bash
# Build image
docker build -t resume-scraper .

# Run container
docker run -p 8000:8000 resume-scraper
```

## 📝 Best Practices

### Performance
- Adjust `SCRAPER_MAX_CONCURRENCY` based on server capacity
- Use appropriate delays to respect target websites
- Monitor memory usage with large PDFs

### Ethical Scraping
- Respect robots.txt files
- Implement reasonable request delays
- Handle rate limiting gracefully
- Consider caching for frequently accessed URLs

### Production Deployment
- Use a production ASGI server (e.g., Gunicorn + Uvicorn)
- Set up proper logging and monitoring
- Configure reverse proxy (Nginx)
- Implement request authentication if needed

## ⚠️ Known Limitations

- **LinkedIn blocking**: LinkedIn URLs typically return HTTP 999
- **JavaScript-heavy sites**: May not extract content from SPAs
- **Rate limiting**: Some sites may block rapid requests
- **PDF formats**: Complex PDF layouts may miss some links

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

For questions, issues, or contributions:

- **Email**: divyanshi122023@gmail.com
- **Issues**: [GitHub Issues](https://github.com/your-username/resume-link-scraper/issues)
- **Documentation**: Available at `/docs` when server is running

---

**Made with ❤️ using FastAPI and Python**
