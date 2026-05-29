/**
 * Abstract storage interface to decouple app logic from browser-specific localStorage.
 * This makes the frontend easy to port to native mobile environments (e.g. React Native / Capacitor)
 * by substituting this implementation with AsyncStorage or a custom mobile database client.
 */

export const storage = {
    getItem(key: string): string | null {
        try {
            if (typeof window !== 'undefined' && window.localStorage) {
                return window.localStorage.getItem(key);
            }
        } catch (e) {
            console.warn('Storage read failed:', e);
        }
        return null;
    },

    setItem(key: string, value: string): void {
        try {
            if (typeof window !== 'undefined' && window.localStorage) {
                window.localStorage.setItem(key, value);
            }
        } catch (e) {
            console.warn('Storage write failed:', e);
        }
    },

    removeItem(key: string): void {
        try {
            if (typeof window !== 'undefined' && window.localStorage) {
                window.localStorage.removeItem(key);
            }
        } catch (e) {
            console.warn('Storage delete failed:', e);
        }
    }
};
