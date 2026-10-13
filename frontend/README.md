# Folio Frontend

Folio is a Personalized Tutoring & Adaptive Learning web application designed to act as a source-grounded AI study companion.

## Features & Architecture

- **React 19 & TypeScript**: Component-driven frontend architecture with strict typing.
- **Vite 8**: High-performance local development server and optimized production bundler.
- **Tailwind CSS v4.3**: CSS-first design system utilizing `@theme` directives and custom variant dark mode.
- **Visual Identity**: Warm ivory surfaces, deep charcoal dark mode, forest green/emerald primary accents, and restrained amber/terracotta indicators.
- **Responsive Layout**: Fluid application shell with collapsible desktop sidebar, slide-over mobile navigation, compact spacing scales, and zero horizontal overflow.
- **Accessibility**: Semantic landmark structure (`header`, `aside`, `nav`, `main`), keyboard navigation, visible focus rings, and reduced-motion support.

## Available Scripts

Inside the `frontend` directory:

- `npm run dev`: Start the Vite local development server (default port `http://localhost:5173`).
- `npm run build`: Type-check with `tsc -b` and produce optimized production bundle in `dist/`.
- `npm run lint`: Run ESLint across all TypeScript and React source files.
- `npm run preview`: Preview the production build locally.

## Environment Configuration

Configure the backend API URL in `.env` (refer to `.env.example`):

```bash
VITE_API_BASE_URL=http://localhost:8000
```
