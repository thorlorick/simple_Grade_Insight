# simple_Grade_Insight
# Grade Insight — Simple Grade Sharing for Schools

**Grade Insight** is a straightforward web application that helps teachers share student grades with parents in real-time. Teachers upload CSV files with grades and assignments, and parents can immediately view their student's progress through a simple web interface.

The multi-tenant architecture allows multiple schools to use the same application independently, with complete data isolation between schools.

---

## ✨ Features

- 🧑🏫 Flexible CSV Upload — Use Grade Insight’s template, or any `.csv` that follows our simplified format -- 
- 🔍 Automatic Data Cleaning — Smart parsing and normalization of grade data -- Allows for unedited Google Classroom CSV uploads.
- 📈 Student/Parent Dashboard — Clean, simple progress visualization
- 🔄 Smart Updates — Intelligent duplicate detection and data merging
- 🐳 Docker Ready — Containerized FastAPI application for easy deployment
- ⚡ Fast Performance — Built on FastAPI for speed and scalability

---

## What It Does

### 🧑‍🏫 For Teachers
- Upload CSV files with student assignments and grades
- Use tags to organize classes, subjects, or assignments
- Each teacher’s data is isolated within their school
- No training or setup required — just upload and go

### 👪 For Parents
- See real-time updates on student progress
- View assignments, marks, teacher comments in almost real time
- Filter by custom tags for easy subject identification
- Access through a school-branded portal (e.g., `yourschool.gradeinsight.com`)

### 🎓 For Students
- View your current grades 
- Stay updated with new marks as teachers upload them
- Access through your unique ID (e.g., `charlie.brown@school1.com')

### 🏫 For Schools
- Host multiple teachers in one deployment with full tenant isolation
- Lightweight, scalable, and easy to self-host
- Keeps school data completely siloed from others

---

## Getting Started

### Requirements
- [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)
- `.env` file (see `.env.example`)
- Valid CSV file matching the expected format

### Quick Start

---

## CSV Format

Grade Insight expects a structured CSV format:

| Row | Description                                  |
|-----|----------------------------------------------|
| 1   | Assignment names (e.g., "Test 1", "Essay")    |
| 2   | Assignment dates (optional)                  |
| 3   | Max points per assignment                    |
| 4+  | Student data rows                            |

**Required student columns:**
- `last_name`
- `first_name`
- `student_email` (used as unique ID)

**Example:**

```csv
last_name,first_name,email,Assignment 1,Assignment 2,Assignment 3
DATE,-,-,2025-06-01,2025-06-03,2025-06-05
POINTS,-,-,100,100,100
Smith,Alice,alice.smith@example.com,85,90,78
Johnson,Bob,bob.johnson@example.com,88,92,81
Brown,Charlie,charlie.brown@example.com,92,85,89
```
---

## Data Processing Pipeline

1. **Upload** - Teacher uploads CSV file through web interface
2. **Parse** - System automatically parses and validates data structure
3. **Clean** - Remove empty columns and normalize data formats
4. **Process** - Insert new records or update existing ones
5. **Report** - Display upload summary with detailed status

---

## Multi-Tenant Architecture

- Each school is fully isolated as a tenant
- School-specific subdomains (e.g., `school1.gradeinsight.com`)
- PostgreSQL supports logical separation via schemas or table prefixes
- Tenants are identified by by their own URL (tenant1.gradeinsight.com or gradeinsight.com/tenant1)
---

## Roadmap

- [ ] Google Classroom integration (no-CSV mode)
- [ ] Admin dashboard for school-wide reporting
- [ ] User authentication and role management

---

## License

This project is licensed under the GNU License.
