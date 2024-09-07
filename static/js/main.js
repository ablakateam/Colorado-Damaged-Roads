document.addEventListener('DOMContentLoaded', function() {
    const submissionForm = document.getElementById('submission-form');
    const commentForm = document.getElementById('comment-form');
    
    if (submissionForm) {
        submissionForm.addEventListener('submit', handleSubmission);
    }
    
    if (commentForm) {
        commentForm.addEventListener('submit', handleComment);
    }
});

function formatDate(dateString) {
    const options = { timeZone: 'America/Denver', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' };
    return new Date(dateString).toLocaleString('en-US', options);
}

async function handleSubmission(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const loadingPopup = document.querySelector('.loading-popup');
    
    try {
        loadingPopup.style.display = 'flex';
        const response = await fetch('/submit', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            alert('Submission successful!');
            window.location.href = `/submission/${result.id}`;
        } else {
            const error = await response.json();
            alert(`Error: ${error.error}`);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred. Please try again.');
    } finally {
        loadingPopup.style.display = 'none';
    }
}

async function handleComment(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    
    try {
        const response = await fetch('/comment', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            const commentContent = formData.get('content');
            addCommentToDOM(commentContent);
            event.target.reset();
        } else {
            const error = await response.json();
            alert(`Error: ${error.error}`);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred. Please try again.');
    }
}

function addCommentToDOM(content) {
    const commentsContainer = document.getElementById('comments-container');
    const commentElement = document.createElement('div');
    commentElement.className = 'bg-gray-100 p-3 rounded mb-2';
    commentElement.innerHTML = `
        <p>${content}</p>
        <p class="text-sm text-gray-500">${formatDate(new Date())}</p>
    `;
    commentsContainer.appendChild(commentElement);
}

// Preview image before upload
const photoInput = document.getElementById('photo');
if (photoInput) {
    photoInput.addEventListener('change', function(event) {
        const file = event.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                const preview = document.createElement('img');
                preview.src = e.target.result;
                preview.className = 'upload-preview';
                const container = photoInput.parentElement;
                const existingPreview = container.querySelector('.upload-preview');
                if (existingPreview) {
                    container.removeChild(existingPreview);
                }
                container.appendChild(preview);
            }
            reader.readAsDataURL(file);
        }
    });
}
