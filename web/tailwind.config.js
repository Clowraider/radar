/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        radar: {
          ink: '#050711',
          panel: '#0b1020',
          line: '#1d2945',
          cyan: '#42e8f4',
          violet: '#8b5cf6',
          amber: '#f8c45c'
        }
      },
      fontFamily: {
        display: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        body: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif']
      },
      boxShadow: {
        glow: '0 0 80px rgba(66, 232, 244, 0.18)',
        violet: '0 0 90px rgba(139, 92, 246, 0.18)'
      },
      animation: {
        float: 'float 8s ease-in-out infinite',
        pulseGlow: 'pulseGlow 4s ease-in-out infinite'
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-12px)' }
        },
        pulseGlow: {
          '0%, 100%': { opacity: '0.55' },
          '50%': { opacity: '0.95' }
        }
      }
    }
  },
  plugins: []
};
