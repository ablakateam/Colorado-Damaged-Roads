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

// ... (keep the existing code)

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
            addCommentToDOM(result.comment.content, result.comment.created_at);
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

function addCommentToDOM(content, timestamp) {
    const commentsContainer = document.getElementById('comments-container');
    const commentElement = document.createElement('div');
    commentElement.className = 'bg-gray-100 p-3 rounded mb-2';
    commentElement.innerHTML = `
        <p>${content}</p>
        <p class="text-sm text-gray-500">${timestamp}</p>
    `;
    commentsContainer.appendChild(commentElement);
}

// ... (keep the rest of the existing code)
