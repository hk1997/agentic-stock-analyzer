import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiFetch } from '../utils/api';
import { storage } from '../utils/storage';

export interface User {
    id: number;
    email: string;
    name?: string;
}

interface AuthContextType {
    user: User | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    login: (token: string, userData: User) => void;
    logout: () => void;
    checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const login = (token: string, userData: User) => {
        storage.setItem('auth_token', token);
        setUser(userData);
    };

    const logout = () => {
        storage.removeItem('auth_token');
        setUser(null);
    };

    const checkAuth = async () => {
        const token = storage.getItem('auth_token');
        if (!token) {
            setIsLoading(false);
            return;
        }

        try {
            const userData = await apiFetch('/api/auth/me');
            setUser(userData);
        } catch (error) {
            console.error('Auth check failed:', error);
            logout();
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        checkAuth();

        const handleUnauthorized = () => logout();
        window.addEventListener('auth_unauthorized', handleUnauthorized);
        
        return () => {
            window.removeEventListener('auth_unauthorized', handleUnauthorized);
        };
    }, []);

    return (
        <AuthContext.Provider value={{ user, isAuthenticated: !!user, isLoading, login, logout, checkAuth }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
