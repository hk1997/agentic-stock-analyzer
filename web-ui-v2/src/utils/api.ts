const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
    const token = localStorage.getItem('auth_token');
    
    const headers = new Headers(options.headers || {});
    if (token) {
        headers.set('Authorization', `Bearer ${token}`);
    }
    
    // Don't set Content-Type if it's FormData (for file uploads, browser will set it with boundary)
    if (!(options.body instanceof FormData)) {
        headers.set('Content-Type', 'application/json');
    }
    
    const config: RequestInit = {
        ...options,
        headers,
    };
    
    const response = await fetch(`${API_BASE}${endpoint}`, config);
    
    if (response.status === 401) {
        // Handle unauthorized (could trigger logout here)
        localStorage.removeItem('auth_token');
        window.dispatchEvent(new Event('auth_unauthorized'));
    }
    
    if (!response.ok) {
        const errorText = await response.text();
        let errorMsg = response.statusText;
        try {
            const errObj = JSON.parse(errorText);
            errorMsg = errObj.detail || errObj.error || errorMsg;
        } catch {
            errorMsg = errorText || errorMsg;
        }
        throw new Error(errorMsg);
    }
    
    return response.json();
}
