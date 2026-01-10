// ==========================================
// Configuration
// ==========================================
const API_BASE_URL = window.location.origin;
const STORAGE_KEY = 'startup_validator_session';

// ==========================================
// State Management
// ==========================================
let currentThreadId = null;

// ==========================================
// DOM Elements
// ==========================================
const elements = {
    // Sections
    welcomeSection: document.getElementById('welcomeSection'),
    validationSection: document.getElementById('validationSection'),
    resultsSection: document.getElementById('resultsSection'),
    loadingOverlay: document.getElementById('loadingOverlay'),
    
    // Navigation
    navbar: document.getElementById('navbar'),
    navbarBrand: document.getElementById('navbarBrand'),
    navHome: document.getElementById('navHome'),
    navValidate: document.getElementById('navValidate'),
    navResults: document.getElementById('navResults'),
    
    // Buttons
    startValidationBtn: document.getElementById('startValidationBtn'),
    backBtn: document.getElementById('backBtn'),
    submitBtn: document.getElementById('submitBtn'),
    newValidationBtn: document.getElementById('newValidationBtn'),
    askFollowupBtn: document.getElementById('askFollowupBtn'),
    
    // Form inputs
    ideaName: document.getElementById('ideaName'),
    description: document.getElementById('description'),
    targetMarket: document.getElementById('targetMarket'),
    problemSolving: document.getElementById('problemSolving'),
    uniqueValue: document.getElementById('uniqueValue'),
    validationForm: document.getElementById('validationForm'),
    
    // Results elements
    resultMeta: document.getElementById('resultMeta'),
    summaryText: document.getElementById('summaryText'),
    strengthsList: document.getElementById('strengthsList'),
    concernsList: document.getElementById('concernsList'),
    stepsList: document.getElementById('stepsList'),
    fullAnalysis: document.getElementById('fullAnalysis'),
    followupQuestion: document.getElementById('followupQuestion'),
    followupAnswer: document.getElementById('followupAnswer'),
    
    // Loading
    loadingText: document.getElementById('loadingText')
};

// ==========================================
// API Functions
// ==========================================
async function validateIdea(ideaData) {
    const response = await fetch(`${API_BASE_URL}/api/validate`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(ideaData)
    });
    
    if (!response.ok) {
        const error = await response.json();
        
        // Handle validation errors (422)
        if (response.status === 422 && error.detail) {
            let errorMessage = 'Please check your input:\n\n';
            
            if (Array.isArray(error.detail)) {
                // FastAPI validation errors
                error.detail.forEach(err => {
                    const field = err.loc ? err.loc[err.loc.length - 1] : 'field';
                    const msg = err.msg || 'Invalid input';
                    errorMessage += `• ${field}: ${msg}\n`;
                });
            } else if (typeof error.detail === 'string') {
                errorMessage = error.detail;
            }
            
            throw new Error(errorMessage);
        }
        
        throw new Error(error.detail || 'Failed to validate idea');
    }
    
    return await response.json();
}

async function askFollowUp(threadId, question) {
    const response = await fetch(`${API_BASE_URL}/api/follow-up`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            thread_id: threadId,
            question: question
        })
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to process follow-up');
    }
    
    return await response.json();
}

async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();
        return data.backboard_connected;
    } catch (error) {
        console.error('Health check failed:', error);
        return false;
    }
}

// ==========================================
// UI Functions
// ==========================================
function showSection(sectionToShow) {
    // Hide all sections
    [elements.welcomeSection, elements.validationSection, elements.resultsSection].forEach(section => {
        if (section) section.style.display = 'none';
    });
    
    // Show the requested section with animation
    if (sectionToShow) {
        sectionToShow.style.display = 'block';
        sectionToShow.classList.add('fade-in');
    }
    
    // Update navbar active states
    updateNavbarState(sectionToShow);
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function updateNavbarState(activeSection) {
    // Remove active class from all nav buttons
    [elements.navHome, elements.navValidate, elements.navResults].forEach(btn => {
        if (btn) btn.classList.remove('active');
    });
    
    // Add active class to current section's nav button
    if (activeSection === elements.welcomeSection) {
        elements.navHome.classList.add('active');
    } else if (activeSection === elements.validationSection) {
        elements.navValidate.classList.add('active');
    } else if (activeSection === elements.resultsSection) {
        elements.navResults.classList.add('active');
        // Show results nav button
        if (elements.navResults) elements.navResults.style.display = 'inline-flex';
    }
}

function showLoading(message = 'Please wait while our AI validates your startup concept...') {
    elements.loadingText.textContent = message;
    elements.loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    elements.loadingOverlay.style.display = 'none';
}

function showError(message) {
    // Create error notification
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-notification';
    errorDiv.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        background: linear-gradient(135deg, #ef4444, #dc2626);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 0.75rem;
        box-shadow: 0 8px 32px rgba(239, 68, 68, 0.3);
        z-index: 10000;
        animation: slideIn 0.3s ease;
        max-width: 450px;
        white-space: pre-line;
        line-height: 1.5;
    `;
    errorDiv.textContent = message;
    
    document.body.appendChild(errorDiv);
    
    // Auto remove after 6 seconds
    setTimeout(() => {
        errorDiv.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => errorDiv.remove(), 300);
    }, 6000);
}

function displayResults(data) {
    // Set metadata
    elements.resultMeta.textContent = `Thread ID: ${data.thread_id}`;
    
    // Set summary with markdown rendering
    if (typeof marked !== 'undefined') {
        elements.summaryText.innerHTML = marked.parse(data.summary);
    } else {
        elements.summaryText.textContent = data.summary;
    }
    
    // Display strengths with markdown rendering
    elements.strengthsList.innerHTML = '';
    if (data.strengths && data.strengths.length > 0) {
        data.strengths.forEach(strength => {
            const li = document.createElement('li');
            if (typeof marked !== 'undefined') {
                li.innerHTML = marked.parseInline(strength);
            } else {
                li.textContent = strength;
            }
            elements.strengthsList.appendChild(li);
        });
    } else {
        elements.strengthsList.innerHTML = '<li>See detailed analysis below</li>';
    }
    
    // Display concerns with markdown rendering
    elements.concernsList.innerHTML = '';
    if (data.concerns && data.concerns.length > 0) {
        data.concerns.forEach(concern => {
            const li = document.createElement('li');
            if (typeof marked !== 'undefined') {
                li.innerHTML = marked.parseInline(concern);
            } else {
                li.textContent = concern;
            }
            elements.concernsList.appendChild(li);
        });
    } else {
        elements.concernsList.innerHTML = '<li>See detailed analysis below</li>';
    }
    
    // Display next steps with markdown rendering
    elements.stepsList.innerHTML = '';
    if (data.next_steps && data.next_steps.length > 0) {
        data.next_steps.forEach(step => {
            const li = document.createElement('li');
            if (typeof marked !== 'undefined') {
                li.innerHTML = marked.parseInline(step);
            } else {
                li.textContent = step;
            }
            elements.stepsList.appendChild(li);
        });
    } else {
        elements.stepsList.innerHTML = '<li>See detailed analysis below</li>';
    }
    
    // Display full analysis with markdown rendering
    if (typeof marked !== 'undefined') {
        elements.fullAnalysis.innerHTML = marked.parse(data.analysis);
    } else {
        // Fallback to plain text if marked.js isn't loaded
        elements.fullAnalysis.textContent = data.analysis;
    }
    
    // Store thread ID for follow-up questions
    currentThreadId = data.thread_id;
    
    // Clear previous follow-up
    elements.followupQuestion.value = '';
    elements.followupAnswer.style.display = 'none';
    
    // Show results section
    showSection(elements.resultsSection);
}

function resetForm() {
    elements.validationForm.reset();
    currentThreadId = null;
}

// ==========================================
// Event Handlers
// ==========================================
// Brand click handler
if (elements.navbarBrand) {
    elements.navbarBrand.addEventListener('click', () => {
        showSection(elements.welcomeSection);
    });
}

// Navigation bar handlers
elements.navHome.addEventListener('click', () => {
    showSection(elements.welcomeSection);
});

elements.navValidate.addEventListener('click', () => {
    showSection(elements.validationSection);
});

elements.navResults.addEventListener('click', () => {
    if (currentThreadId) {
        showSection(elements.resultsSection);
    } else {
        showError('No validation results available');
    }
});

elements.startValidationBtn.addEventListener('click', () => {
    showSection(elements.validationSection);
});

elements.backBtn.addEventListener('click', () => {
    showSection(elements.welcomeSection);
});

elements.validationForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Get form data
    console.log('Gathering form data...');
    const ideaData = {
        idea_name: elements.ideaName.value.trim(),
        description: elements.description.value.trim(),
        target_market: elements.targetMarket.value.trim(),
        problem_solving: elements.problemSolving.value.trim(),
        unique_value: elements.uniqueValue.value.trim() || null
    };
    console.log('Form data gathered:', ideaData);
    
    // Validate required fields
    if (!ideaData.idea_name || !ideaData.description || !ideaData.target_market || !ideaData.problem_solving) {
        showError('Please fill in all required fields');
        return;
    }
    
    // Client-side length validation
    const minLength = 20;
    if (ideaData.description.length < minLength) {
        showError(`Description is too short. Please provide at least ${minLength} characters to get a meaningful analysis.`);
        return;
    }
    
    if (ideaData.problem_solving.length < minLength) {
        showError(`Problem description is too short. Please provide at least ${minLength} characters to help us understand the issue better.`);
        return;
    }
    
    if (ideaData.idea_name.length < 3) {
        showError('Idea name is too short. Please provide a meaningful name (at least 3 characters).');
        return;
    }
    
    if (ideaData.target_market.length < 3) {
        showError('Target market description is too short. Please describe your target audience (at least 3 characters).');
        return;
    }
    
    try {
        showLoading('Analyzing your startup idea... This may take a moment.');
        
        // Submit for validation
        const result = await validateIdea(ideaData);
        
        hideLoading();
        
        // Display results
        displayResults(result);
        
        // Save to session storage
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
            ideaData,
            result,
            timestamp: new Date().toISOString()
        }));
        
    } catch (error) {
        hideLoading();
        console.error('Validation error:', error);
        showError(error.message || 'Failed to validate idea. Please try again.');
    }
});

elements.newValidationBtn.addEventListener('click', () => {
    resetForm();
    showSection(elements.validationSection);
});

elements.askFollowupBtn.addEventListener('click', async () => {
    const question = elements.followupQuestion.value.trim();
    
    if (!question) {
        showError('Please enter a question');
        return;
    }
    
    if (!currentThreadId) {
        showError('No active validation session');
        return;
    }
    
    try {
        elements.askFollowupBtn.disabled = true;
        elements.askFollowupBtn.textContent = 'Asking...';
        
        const result = await askFollowUp(currentThreadId, question);
        
        // Display answer with markdown rendering
        if (typeof marked !== 'undefined') {
            elements.followupAnswer.innerHTML = marked.parse(result.answer);
        } else {
            elements.followupAnswer.textContent = result.answer;
        }
        elements.followupAnswer.style.display = 'block';
        
        // Clear question
        elements.followupQuestion.value = '';
        
    } catch (error) {
        console.error('Follow-up error:', error);
        showError(error.message || 'Failed to process question. Please try again.');
    } finally {
        elements.askFollowupBtn.disabled = false;
        elements.askFollowupBtn.innerHTML = '<span>Ask</span>';
    }
});

// Allow Enter key to submit follow-up
elements.followupQuestion.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        elements.askFollowupBtn.click();
    }
});

// ==========================================
// Initialization
// ==========================================
document.addEventListener('DOMContentLoaded', async () => {
    // Check backend health
    const isHealthy = await checkHealth();
    
    if (!isHealthy) {
        console.warn('Backend service may not be fully connected to Backboard.io');
        // You could show a warning banner here if desired
    }
    
    // Check for saved session
    const savedSession = sessionStorage.getItem(STORAGE_KEY);
    if (savedSession) {
        try {
            const session = JSON.parse(savedSession);
            // Optionally restore previous results
            // displayResults(session.result);
        } catch (error) {
            console.error('Failed to restore session:', error);
            sessionStorage.removeItem(STORAGE_KEY);
        }
    }
    
    // Show welcome section by default
    showSection(elements.welcomeSection);
    
    console.log('✨ Startup Validator initialized');
});

// Add CSS animations dynamically
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
