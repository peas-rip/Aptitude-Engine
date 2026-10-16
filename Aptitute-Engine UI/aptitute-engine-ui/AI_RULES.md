# Tech Stack & Library Usage Rules

- **Framework**: React 18 with TypeScript for type safety.
- **Routing**: React Router (v6) – keep all route definitions in `src/App.tsx`.
- **Styling**: Tailwind CSS for utility‑first styling; apply Tailwind classes directly in JSX.
- **UI Components**: Use the pre‑built shadcn/ui component library (Radix‑based) for all common UI elements (buttons, inputs, modals, tables, etc.). Do **not** modify the shipped shadcn/ui files; create new wrapper components if customization is needed.
- **Icons**: Use `lucide-react` for icons; import individual icons as needed.
- **State Management**: Prefer React’s built‑in hooks (`useState`, `useEffect`, `useContext`) or lightweight libraries like Zustand only when explicitly required.
- **Forms & Validation**: Use React Hook Form with Zod schema validation (both already configured with shadcn/ui).
- **API Calls**: Use `fetch` or Axios (if added) inside service functions; keep API logic separate from components.
- **File Organization**:
  - Source code lives in the `src/` folder.
  - Pages go in `src/pages/` (the default page is `src/pages/Index.tsx`).
  - Reusable components go in `src/components/`.
  - Always update `src/pages/Index.tsx` (or the relevant page) to render new components so they appear in the UI.
- **Code Style**: Write clean, readable TypeScript; avoid `any` unless unavoidable; prefer functional components with arrow function syntax.