// shared-utils.js - Common utilities for grade system
class GradeUtils {
    static escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    static escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    static formatDate(dateString) {
        if (!dateString) return 'No date';
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }

    static isValidEmail(email) {
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailPattern.test(email);
    }

    static getGradeClass(percentage) {
        if (percentage >= 80) return 'grade-good';
        if (percentage >= 60) return 'grade-medium';
        return 'grade-poor';
    }

    static getGradeLetter(percentage) {
        if (percentage >= 90) return 'A';
        if (percentage >= 80) return 'B';
        if (percentage >= 70) return 'C';
        if (percentage >= 60) return 'D';
        return 'F';
    }

    static calculatePercentage(score, maxPoints) {
        return maxPoints > 0 ? Math.round((score / maxPoints) * 100) : 0;
    }

    static async fetchWithErrorHandling(url) {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    }

    // Existing showError function (can be improved or kept as is)
    static showError(containerId, message, colSpan = 1) {
        const container = document.getElementById(containerId);
        if (container) {
            // Clear existing content and set error message
            if (container.tagName === 'TBODY') {
                container.innerHTML = `
                    <tr>
                        <td colspan="${colSpan}" class="error">
                            ${this.escapeHtml(message)}
                        </td>
                    </tr>
                `;
            } else {
                container.innerHTML = `
                    <div class="error">
                        <strong>Error:</strong> ${this.escapeHtml(message)}
                    </div>
                `;
                container.style.display = 'block';
            }
        }
    }

    // New generic notification function for messages (can be used for success/error)
    static showNotification(containerId, message, type = 'info') {
        const container = document.getElementById(containerId);
        if (container) {
            container.textContent = message;
            container.className = `message ${type}`; // Add a class for styling (e.g., 'message success', 'message error')
            container.style.display = 'block';
            // Optional: Hide after some time if it's not a critical error
            if (type === 'success' || type === 'info') {
                setTimeout(() => {
                    container.style.display = 'none';
                    container.textContent = '';
                }, 5000); // Hide after 5 seconds
            }
        }
    }
}


// Utility functions
            function showMessage(message, type = 'info') {
                const messageClass = type === 'error' ? 'error' : type === 'success' ? 'success' : 'loading';
                messageContainer.innerHTML = `<div class="${messageClass}">${GradeUtils.escapeHtml(message)}</div>`;
                messageContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }

            function clearMessage() {
                messageContainer.innerHTML = '';
            }

            function formatFileSize(bytes) {
                if (bytes === 0) return '0 Bytes';
                const k = 1024;
                const sizes = ['Bytes', 'KB', 'MB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
            }

            function setLoadingState(loading) {
                submitBtn.disabled = loading;
                submitText.style.display = loading ? 'none' : 'inline';
                loadingSpinner.style.display = loading ? 'inline-flex' : 'none';
                
                fileInput.disabled = loading;
            }

            function showProgress() {
                progressSection.style.display = 'block';
                progressSection.scrollIntoView({ behavior: 'smooth' });
            }

            function hideProgress() {
                progressSection.style.display = 'none';
            }

            function updateProgressStep(stepNumber, status) {
                const step = document.getElementById(`step${stepNumber}`);
                if (step) {
                    if (status === 'active') {
                        step.style.color = '#4f46e5';
                        step.style.fontWeight = '600';
                    } else if (status === 'complete') {
                        step.style.color = '#059669';
                        step.style.fontWeight = '600';
                    }
                }
            }

            // File input handling
                const fileInput = document.getElementById('fileInput'); // Add this line
                const fileInfo = document.getElementById('fileInfo'); // You'll likely need this too

            fileInput.addEventListener('change', function(event) {
                const file = event.target.files[0];
                if (file) {
                    if (!file.name.toLowerCase().endsWith('.csv')) {
                        showMessage('Please select a CSV file.', 'error');
                        fileInput.value = '';
                        fileInfo.style.display = 'none';
                        return;
                    }
                    
                    fileInfo.textContent = `Selected: ${file.name} (${formatFileSize(file.size)})`;
                    fileInfo.style.display = 'block';
                    clearMessage();
                } else {
                    fileInfo.style.display = 'none';
                }
            });

            // Form submission
            form.addEventListener('submit', async function(event) {
                event.preventDefault();
                
                if (!fileInput.files[0]) {
                    showMessage('Please select a CSV file.', 'error');
                    return;
                }

                setLoadingState(true);
                showProgress();
                clearMessage();

                try {
                    updateProgressStep(1, 'active');
                    
                    const formData = new FormData();
                    formData.append('file', fileInput.files[0]);
                    formData.append('teacher_name', 'DefaultTeacher'); // You may want to get this from a form field or user session
                    formData.append('class_tag', 'DefaultClass'); // You may want to get this from a form field or user session

                    updateProgressStep(3, 'active');

                    const response = await fetch('/upload', {
                        method: 'POST',
                        body: formData,
                    });

                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({}));
                        throw new Error(errorData.error || `Upload failed with status ${response.status}`);
                    }

                    const result = await response.json();
                    updateProgressStep(4, 'complete');
                    showMessage('File uploaded successfully! Redirecting to dashboard...', 'success');
                    
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 2000);

                } catch (error) {
                    console.error('Upload error:', error);
                    showMessage(`Upload failed: ${error.message}`, 'error');
                    setLoadingState(false);
                    hideProgress();
                }
            }
                                 );
        

// grades-table.js - Enhanced grades table with tag search
class GradesTable {
    constructor() {
        this.allStudents = [];
        this.filteredStudents = [];
        this.assignments = [];
        this.currentStudentSearch = '';
        this.currentTagSearch = '';
        this.visibleColumns = new Set();
        this.init();
    }

    init() {
        this.loadGrades();
        this.setupSearch();
        this.setupTagSearch();
    }

    async loadGrades() {
        try {
            const data = await GradeUtils.fetchWithErrorHandling('/api/grades-table');
            this.allStudents = data.students || [];
            this.filteredStudents = [...this.allStudents];
            this.extractAssignments();
            this.renderTable();
            this.updateSearchStats();
        } catch (error) {
            console.error('Error loading grades:', error);
            GradeUtils.showError('tableBody', 'Failed to load grades. Please refresh the page.', this.assignments.length + 1);
        }
    }

    extractAssignments() {
        const assignmentMap = new Map();
        this.allStudents.forEach(student => {
            student.grades.forEach(grade => {
                const key = `${grade.assignment}|${grade.date}`;
                if (!assignmentMap.has(key)) {
                    assignmentMap.set(key, {
                        name: grade.assignment,
                        date: grade.date,
                        max_points: grade.max_points,
                        tags: grade.tags || [] // Assuming your grade data includes tags
                    });
                }
            });
        });
        this.assignments = Array.from(assignmentMap.values());
        this.assignments.sort((a, b) => {
            if (a.date && b.date) return new Date(a.date) - new Date(b.date);
            return a.name.localeCompare(b.name);
        });
        
        // Initialize all columns as visible
        this.visibleColumns = new Set(this.assignments.map((_, index) => index));
    }

    setupSearch() {
        const searchInput = document.getElementById('studentSearch');
        const clearButton = document.getElementById('clearSearch');

        if (searchInput) {
            searchInput.addEventListener('input', () => {
                const query = searchInput.value.trim();
                this.currentStudentSearch = query;
                this.applyFilters();
                if (query) {
                    clearButton.style.display = 'inline-block';
                } else {
                    clearButton.style.display = 'none';
                }
            });
        }

        if (clearButton) {
            clearButton.addEventListener('click', () => this.clearStudentSearch());
        }

        if (searchInput) {
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') e.preventDefault();
            });
        }
    }

    setupTagSearch() {
        // Create tag search input if it doesn't exist
        const searchContainer = document.querySelector('.search-container') || document.querySelector('.controls');
        if (searchContainer && !document.getElementById('tagSearch')) {
            const tagSearchHTML = `
                <div class="search-group">
                    <label for="tagSearch">Filter by Assignment Tag:</label>
                    <input type="text" id="tagSearch" placeholder="Enter tag to filter assignments..." />
                    <button type="button" id="clearTagSearch" style="display: none;">Clear</button>
                </div>
            `;
            searchContainer.insertAdjacentHTML('beforeend', tagSearchHTML);
        }

        const tagSearchInput = document.getElementById('tagSearch');
        const clearTagButton = document.getElementById('clearTagSearch');

        if (tagSearchInput) {
            tagSearchInput.addEventListener('input', () => {
                const query = tagSearchInput.value.trim();
                this.currentTagSearch = query;
                this.applyTagFilter();
                if (query) {
                    clearTagButton.style.display = 'inline-block';
                } else {
                    clearTagButton.style.display = 'none';
                }
            });
        }

        if (clearTagButton) {
            clearTagButton.addEventListener('click', () => this.clearTagSearch());
        }
    }

    applyFilters() {
        // Apply student name/email filter
        if (this.currentStudentSearch) {
            const searchTerm = this.currentStudentSearch.toLowerCase();
            this.filteredStudents = this.allStudents.filter(student => {
                const fullName = `${student.first_name} ${student.last_name}`.toLowerCase();
                const reverseName = `${student.last_name}, ${student.first_name}`.toLowerCase();
                const email = student.email.toLowerCase();
                return fullName.includes(searchTerm) || reverseName.includes(searchTerm) || email.includes(searchTerm);
            });
        } else {
            this.filteredStudents = [...this.allStudents];
        }
        
        this.renderBody();
        this.updateSearchStats();
    }

    applyTagFilter() {
        if (!this.currentTagSearch) {
            // Show all columns
            this.visibleColumns = new Set(this.assignments.map((_, index) => index));
        } else {
            // Filter columns by tag
            const searchTerm = this.currentTagSearch.toLowerCase();
            this.visibleColumns = new Set();
            
            this.assignments.forEach((assignment, index) => {
                // Check if assignment name contains the search term
                if (assignment.name.toLowerCase().includes(searchTerm)) {
                    this.visibleColumns.add(index);
                }
                // Check if any tags contain the search term
                if (assignment.tags && assignment.tags.some(tag => 
                    tag.toLowerCase().includes(searchTerm))) {
                    this.visibleColumns.add(index);
                }
            });
        }
        
        this.renderTable();
        this.updateSearchStats();
    }

    renderTable() {
        this.renderHeader();
        this.renderBody();
    }

    renderHeader() {
        const headerRow = document.getElementById('tableHeader');
        headerRow.innerHTML = '<th class="student-info">Student</th>';
        
        this.assignments.forEach((assignment, index) => {
            const th = document.createElement('th');
            th.className = 'assignment-header';
            th.style.display = this.visibleColumns.has(index) ? '' : 'none';
            
            const tagsHTML = assignment.tags && assignment.tags.length > 0 
                ? `<div class="assignment-tags">${assignment.tags.map(tag => 
                    `<span class="tag">${GradeUtils.escapeHtml(tag)}</span>`).join('')}</div>`
                : '';
            
            th.innerHTML = `
                <div class="assignment-name">${GradeUtils.escapeHtml(assignment.name)}</div>
                <div class="assignment-info">
                    ${assignment.date ? GradeUtils.formatDate(assignment.date) : 'No date'} | 
                    ${assignment.max_points} pts
                </div>
                ${tagsHTML}
            `;
            headerRow.appendChild(th);
        });
    }

    renderBody() {
        const tbody = document.getElementById('tableBody');
        tbody.innerHTML = '';
        
        if (this.filteredStudents.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = `<td colspan="${this.assignments.length + 1}" class="no-results">
                ${this.allStudents.length === 0 ? 'No students found in database.' : 'No students match your search.'}
            </td>`;
            tbody.appendChild(row);
            return;
        }

        this.filteredStudents.forEach(student => {
            const row = this.createStudentRow(student);
            tbody.appendChild(row);
        });
    }

    createStudentRow(student) {
        const row = document.createElement('tr');
        
        // Add interactivity
        row.style.cursor = 'pointer';
        row.classList.add('clickable-row');
        row.addEventListener('click', () => this.navigateToStudent(student));

        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#d4edda';
            this.style.transition = 'background-color 0.2s ease';
        });

        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });

        // Student info cell
        const studentCell = document.createElement('td');
        studentCell.className = 'student-info';
        studentCell.innerHTML = `
            <div class="student-name">${this.highlightText(GradeUtils.escapeHtml(`${student.last_name}, ${student.first_name}`))}</div>
            <div class="student-email">${this.highlightText(GradeUtils.escapeHtml(student.email))}</div>
        `;
        row.appendChild(studentCell);

        // Grade cells
        this.assignments.forEach((assignment, index) => {
            const gradeCell = this.createGradeCell(student, assignment);
            gradeCell.style.display = this.visibleColumns.has(index) ? '' : 'none';
            row.appendChild(gradeCell);
        });

        return row;
    }

    createGradeCell(student, assignment) {
        const gradeCell = document.createElement('td');
        gradeCell.className = 'grade-cell';
        const grade = student.grades.find(g => g.assignment === assignment.name && g.date === assignment.date);
        
        if (grade) {
            const percentage = GradeUtils.calculatePercentage(grade.score, grade.max_points);
            const gradeClass = GradeUtils.getGradeClass(percentage);
            gradeCell.innerHTML = `
                <div class="grade-score ${gradeClass}">${grade.score}/${grade.max_points}</div>
                <div class="grade-percentage">${percentage}%</div>
            `;
        } else {
            gradeCell.innerHTML = '<div class="no-grade">—</div>';
        }
        
        return gradeCell;
    }

    navigateToStudent(student) {
        if (student.email) {
            window.location.href = `/teacher-student-view?email=${encodeURIComponent(student.email)}`;
        } else {
            console.error('Student email not found:', student);
            alert('Unable to navigate to student profile - email not found.');
        }
    }

    clearStudentSearch() {
        const searchInput = document.getElementById('studentSearch');
        if (searchInput) {
            searchInput.value = '';
        }
        document.getElementById('clearSearch').style.display = 'none';
        this.currentStudentSearch = '';
        this.applyFilters();
    }

    clearTagSearch() {
        const tagSearchInput = document.getElementById('tagSearch');
        if (tagSearchInput) {
            tagSearchInput.value = '';
        }
        document.getElementById('clearTagSearch').style.display = 'none';
        this.currentTagSearch = '';
        this.applyTagFilter();
    }

    updateSearchStats() {
        const statsElement = document.getElementById('searchStats');
        if (statsElement) {
            const visibleAssignments = this.visibleColumns.size;
            const totalAssignments = this.assignments.length;
            
            let statusText = '';
            if (this.currentStudentSearch || this.currentTagSearch) {
                const parts = [];
                if (this.currentStudentSearch) {
                    parts.push(`${this.filteredStudents.length} of ${this.allStudents.length} students`);
                }
                if (this.currentTagSearch) {
                    parts.push(`${visibleAssignments} of ${totalAssignments} assignments`);
                }
                statusText = `Showing ${parts.join(', ')}`;
            } else {
                statusText = `${this.allStudents.length} students, ${totalAssignments} assignments`;
            }
            
            statsElement.textContent = statusText;
        }
    }

    highlightText(text) {
        const searchTerm = this.currentStudentSearch;
        if (!searchTerm) return text;
        const regex = new RegExp(`(${GradeUtils.escapeRegex(searchTerm)})`, 'gi');
        return text.replace(regex, '<span class="highlight">$1</span>');
    }
}

// Enhanced student-portal.js with tag filtering (keep this as is)
class StudentGradePortal {
    constructor() {
        this.emailInput = document.getElementById('emailInput');
        this.searchBtn = document.getElementById('searchBtn');
        this.clearBtn = document.getElementById('clearBtn');
        this.resultsSection = document.getElementById('resultsSection');
        this.searchStats = document.getElementById('searchStats');
        
        // Tag filtering properties
        this.allGrades = [];
        this.filteredGrades = [];
        this.availableTags = [];
        this.selectedTags = [];
        this.currentStudent = null;
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.handleURLParams();
    }

    bindEvents() {
        this.searchBtn.addEventListener('click', () => this.searchGrades());
        this.clearBtn.addEventListener('click', () => this.clearResults());
        
        this.emailInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.searchGrades();
        });

        this.emailInput.addEventListener('input', () => {
            if (this.emailInput.value.trim() === '') this.clearResults();
        });
    }

    handleURLParams() {
        const params = new URLSearchParams(window.location.search);
        const emailFromURL = params.get('email');
        if (emailFromURL) {
            this.emailInput.value = decodeURIComponent(emailFromURL);
            this.searchGrades();
        }
    }

    clearResults() {
        this.resultsSection.style.display = 'none';
        this.clearBtn.style.display = 'none';
        this.searchStats.style.display = 'none';
        this.emailInput.value = '';
        this.emailInput.focus();
        
        // Reset tag filtering
        this.allGrades = [];
        this.filteredGrades = [];
        this.availableTags = [];
        this.selectedTags = [];
        this.currentStudent = null;
    }

    async searchGrades() {
        const email = this.emailInput.value.trim();
        
        if (!email) {
            this.showError('Please enter your email address.');
            return;
        }

        if (!GradeUtils.isValidEmail(email)) {
            this.showError('Please enter a valid email address.');
            return;
        }

        try {
            this.showLoading();
            this.searchBtn.disabled = true;
            this.clearBtn.style.display = 'inline-block';
            
            const response = await fetch(`/api/student/${encodeURIComponent(email)}`);
            
            if (response.status === 404) {
                this.showNotFound(email);
                return;
            }

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const studentData = await response.json();
            this.currentStudent = studentData;
            this.allGrades = studentData.grades || [];
            this.filteredGrades = [...this.allGrades];
            
            // Extract and setup tags
            this.extractAvailableTags();
            this.displayStudentGrades(studentData);
            
        } catch (error) {
            console.error('Error fetching student grades:', error);
            this.showError('Unable to fetch grades. Please try again later.');
        } finally {
            this.searchBtn.disabled = false;
        }
    }

    extractAvailableTags() {
        const tagSet = new Set();
        
        this.allGrades.forEach(grade => {
            // Check different possible tag formats
            if (grade.tags) {
                if (Array.isArray(grade.tags)) {
                    // Tags as array: ["math", "quiz"]
                    grade.tags.forEach(tag => tagSet.add(tag.toLowerCase()));
                } else if (typeof grade.tags === 'string') {
                    // Tags as comma-separated string: "math,quiz"
                    grade.tags.split(',').forEach(tag => tagSet.add(tag.trim().toLowerCase()));
                }
            }
            
            // Alternative: tags might be on assignment level
            if (grade.assignment_tags) {
                if (Array.isArray(grade.assignment_tags)) {
                    grade.assignment_tags.forEach(tag => tagSet.add(tag.toLowerCase()));
                } else if (typeof grade.assignment_tags === 'string') {
                    grade.assignment_tags.split(',').forEach(tag => tagSet.add(tag.trim().toLowerCase()));
                }
            }
        });
        
        this.availableTags = Array.from(tagSet).sort();
    }

    createTagFilterSection() {
        if (this.availableTags.length === 0) {
            return ''; // No tags available
        }

        const tagButtons = this.availableTags.map(tag => {
            const isSelected = this.selectedTags.includes(tag);
            const activeClass = isSelected ? 'active' : '';
            return `<button class="tag-button ${activeClass}" data-tag="${tag}">
                ${GradeUtils.escapeHtml(tag)}
            </button>`;
        }).join('');

        return `
            <div class="tag-filter-section" id="tagFilterSection">
                <div class="tag-filter-title">Filter by Tags</div>
                <div class="tag-controls" id="tagControls">
                    ${tagButtons}
                </div>
                <div class="filter-actions">
                    <button class="filter-btn" id="clearTagsBtn">Clear All</button>
                    <div class="filter-stats" id="filterStats">
                        ${this.getFilterStatsText()}
                    </div>
                </div>
            </div>
        `;
    }

    setupTagFilterEvents() {
        const tagFilterSection = document.getElementById('tagFilterSection');
        if (!tagFilterSection) return;

        // Tag button clicks
        const tagButtons = tagFilterSection.querySelectorAll('.tag-button');
        tagButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const tag = e.target.dataset.tag;
                this.toggleTag(tag);
            });
        });

        // Clear all tags button
        const clearTagsBtn = document.getElementById('clearTagsBtn');
        if (clearTagsBtn) {
            clearTagsBtn.addEventListener('click', () => {
                this.clearAllTags();
            });
        }
    }

    toggleTag(tag) {
        const index = this.selectedTags.indexOf(tag);
        if (index > -1) {
            // Remove tag
            this.selectedTags.splice(index, 1);
        } else {
            // Add tag
            this.selectedTags.push(tag);
        }
        
        this.updateTagButtons();
        this.applyTagFilter();
    }

    clearAllTags() {
        this.selectedTags = [];
        this.updateTagButtons();
        this.applyTagFilter();
    }

    updateTagButtons() {
        const tagButtons = document.querySelectorAll('.tag-button');
        tagButtons.forEach(button => {
            const tag = button.dataset.tag;
            if (this.selectedTags.includes(tag)) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }

    applyTagFilter() {
        if (this.selectedTags.length === 0) {
            // No tags selected, show all grades
            this.filteredGrades = [...this.allGrades];
        } else {
            // Filter grades that have at least one of the selected tags
            this.filteredGrades = this.allGrades.filter(grade => {
                const gradeTags = this.getGradeTags(grade);
                return this.selectedTags.some(selectedTag => 
                    gradeTags.includes(selectedTag)
                );
            });
        }

        // Update the display
        this.updateGradesTable();
        this.updateFilterStats();
    }

    getGradeTags(grade) {
        const tags = [];
        
        if (grade.tags) {
            if (Array.isArray(grade.tags)) {
                tags.push(...grade.tags.map(tag => tag.toLowerCase()));
            } else if (typeof grade.tags === 'string') {
                tags.push(...grade.tags.split(',').map(tag => tag.trim().toLowerCase()));
            }
        }
        
        if (grade.assignment_tags) {
            if (Array.isArray(grade.assignment_tags)) {
                tags.push(...grade.assignment_tags.map(tag => tag.toLowerCase()));
            } else if (typeof grade.assignment_tags === 'string') {
                tags.push(...grade.assignment_tags.split(',').map(tag => tag.trim().toLowerCase()));
            }
        }
        
        return [...new Set(tags)]; // Remove duplicates
    }

    updateGradesTable() {
        const tableContainer = document.querySelector('.grades-table-container');
        if (tableContainer) {
            const gradesTableHtml = this.filteredGrades.length > 0 
                ? this.generateGradesTable(this.filteredGrades)
                : '<p class="no-data">No assignments match the selected tags.</p>';
            
            tableContainer.innerHTML = gradesTableHtml;
        }
    }

    updateFilterStats() {
        const filterStats = document.getElementById('filterStats');
        if (filterStats) {
            filterStats.textContent = this.getFilterStatsText();
        }
    }

    getFilterStatsText() {
        if (this.selectedTags.length === 0) {
            return `Showing all ${this.allGrades.length} assignments`;
        } else {
            return `Showing ${this.filteredGrades.length} of ${this.allGrades.length} assignments (${this.selectedTags.join(', ')})`;
        }
    }

    displayStudentGrades(student) {
        const overallPercentage = this.calculateFilteredOverallPercentage();
        const gradeClass = GradeUtils.getGradeClass(overallPercentage);
        const gradeLetter = GradeUtils.getGradeLetter(overallPercentage);
        
        const tagFilterHtml = this.createTagFilterSection();
        
        const gradesTableHtml = this.filteredGrades.length > 0 
            ? this.generateGradesTable(this.filteredGrades)
            : '<p class="no-data">No assignments found.</p>';

        this.searchStats.textContent = `Found ${student.total_assignments || 0} assignments for ${student.first_name} ${student.last_name}`;
        this.searchStats.style.display = 'block';

        this.resultsSection.innerHTML = `
            <div class="student-header">
                <div class="student-name">${GradeUtils.escapeHtml(student.first_name)} ${GradeUtils.escapeHtml(student.last_name)}</div>
                <div class="student-email">${GradeUtils.escapeHtml(student.email)}</div>
                
                <div class="overall-stats">
                    <div class="stat-box">
                        <span class="stat-value">${this.filteredGrades.length}</span>
                        <div class="stat-label">${this.selectedTags.length > 0 ? 'Filtered' : 'Total'} Assignments</div>
                    </div>
                    <div class="stat-box">
                        <span class="stat-value">${this.calculateFilteredPoints()}</span>
                        <div class="stat-label">Points Earned</div>
                    </div>
                    <div class="stat-box">
                        <span class="stat-value">${this.calculateFilteredMaxPoints()}</span>
                        <div class="stat-label">Points Possible</div>
                    </div>
                </div>
                
                <div class="overall-grade ${gradeClass}">
                    ${this.selectedTags.length > 0 ? 'Filtered' : 'Overall'} Grade: ${overallPercentage.toFixed(1)}% (${gradeLetter})
                </div>
            </div>
            
            ${tagFilterHtml}
            
            <div class="grades-table-container">
                ${gradesTableHtml}
            </div>
        `;

        this.resultsSection.style.display = 'block';
        this.resultsSection.scrollIntoView({ behavior: 'smooth' });
        
        // Setup tag filter events after DOM is updated
        this.setupTagFilterEvents();
        
        // Show tag filter section if tags are available
        if (this.availableTags.length > 0) {
            const tagSection = document.getElementById('tagFilterSection');
            if (tagSection) tagSection.style.display = 'block';
        }
    }

    calculateFilteredOverallPercentage() {
        if (this.filteredGrades.length === 0) return 0;
        
        const totalPoints = this.calculateFilteredPoints();
        const maxPoints = this.calculateFilteredMaxPoints();
        
        return maxPoints > 0 ? (totalPoints / maxPoints) * 100 : 0;
    }

    calculateFilteredPoints() {
        return this.filteredGrades.reduce((sum, grade) => sum + (grade.score || 0), 0);
    }

    calculateFilteredMaxPoints() {
        return this.filteredGrades.reduce((sum, grade) => sum + (grade.max_points || 0), 0);
    }

    generateGradesTable(grades) {
        const tableRows = grades.map(grade => {
            const percentage = GradeUtils.calculatePercentage(grade.score, grade.max_points);
            const gradeClass = GradeUtils.getGradeClass(percentage);
            const date = grade.date ? GradeUtils.formatDate(grade.date) : 'No date';
            
            // Display tags if available
            const tags = this.getGradeTags(grade);
            const tagDisplay = tags.length > 0 
                ? `<div class="assignment-tags">${tags.map(tag => `<span class="tag">${GradeUtils.escapeHtml(tag)}</span>`).join('')}</div>`
                : '';
            
            return `
                <tr>
                    <td>
                        <div class="assignment-name">${GradeUtils.escapeHtml(grade.assignment)}</div>
                        <div class="assignment-date">${date}</div>
                        ${tagDisplay}
                    </td>
                    <td class="score-cell">${grade.score} / ${grade.max_points}</td>
                    <td class="percentage-cell">
                        <span class="percentage-badge ${gradeClass}">
                            ${percentage.toFixed(1)}%
                        </span>
                    </td>
                </tr>
            `;
        }).join('');

        return `
            <table class="grades-table">
                <thead>
                    <tr>
                        <th>Assignment</th>
                        <th style="text-align: center;">Score</th>
                        <th style="text-align: center;">Percentage</th>
                    </tr>
                </thead>
                <tbody>
                    ${tableRows}
                </tbody>
            </table>
        `;
    }

    showLoading() {
        this.resultsSection.innerHTML = `
            <div class="loading">
                <div class="loading-spinner"></div>
                Loading your grades...
            </div>
        `;
        this.resultsSection.style.display = 'block';
    }

    showError(message) {
        GradeUtils.showError('resultsSection', message);
    }

    showNotFound(email) {
        this.resultsSection.innerHTML = `
            <div class="not-found">
                <h3>Student Not Found</h3>
                <p>No student found with email address: <strong>${GradeUtils.escapeHtml(email)}</strong></p>
                <p>Please check your email address and try again.</p>
            </div>
        `;
        this.resultsSection.style.display = 'block';
    }
}

 // Enhanced search functionality for both students and tags (keep this as is)
    document.addEventListener('DOMContentLoaded', function() {
        const studentSearchInput = document.getElementById('studentSearch');
        const tagSearchInput = document.getElementById('tagSearch');
        const clearStudentButton = document.getElementById('clearStudentSearch');
        const clearTagButton = document.getElementById('clearTagSearch');
        const searchStats = document.getElementById('searchStats');
        
        let currentStudentFilter = '';
        let currentTagFilter = '';
        let allAssignmentColumns = [];
        
        // Store column information when table loads
        function initializeColumnData() {
            const headerRow = document.getElementById('tableHeader');
            const headers = Array.from(headerRow.children).slice(1); // Skip student column
            
            allAssignmentColumns = headers.map((header, index) => ({
                index: index + 1, // +1 because we skip student column
                element: header,
                name: header.textContent.toLowerCase(),
                tags: (header.getAttribute('data-tags') || '').toLowerCase().split(',').filter(tag => tag.trim())
            }));
        }
        
    });
