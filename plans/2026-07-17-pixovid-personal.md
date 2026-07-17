# PixoVid Personal — Implementation Plan

> **For Codex:** Build this plan task-by-task. This is a PERSONAL tool, not a SaaS.

**Goal:** Fork PixoVid and strip it into a personal AI video creation tool — prompt → image → face swap → video — for Eddie's content creation.

**Architecture:** Fork the open-source PixoVid repo (github.com/codes30/pixovid). Remove all SaaS features (auth, payments, credits, user management, S3). Keep the core pipeline: text prompt → image generation → face swap → video generation. Add a simple local file storage layer.

**Tech Stack:** React + Vite + TypeScript + Tailwind (frontend), Express + TypeScript (backend), SQLite (replaces Postgres for personal use), FaceFusion Docker (face swap), OpenRouter API (video/image gen).

---

## Phase 1: Fork & Strip SaaS Layer

### Task 1: Clone and Initialize
**Objective:** Get the PixoVid repo local and working.

**Steps:**
1. Clone `https://github.com/codes30/pixovid` to `D:/pixovid-personal/`
2. Run `bun install` to get dependencies
3. Read through the project structure to understand what exists
4. Create a new git branch: `git checkout -b personal-build`

**Verify:** `bun install` completes without errors.

---

### Task 2: Strip Authentication & User Management
**Objective:** Remove all auth (better-auth), user accounts, session management.

**Files to modify/remove:**
- Remove: `apps/backend/src/lib/auth.ts` (or similar auth module)
- Remove: All auth middleware/routes
- Remove: Google OAuth configuration
- Modify: Backend routes to remove auth checks
- Modify: Frontend to remove login/signup/profile pages

**Steps:**
1. Find all auth-related files: `grep -r "better-auth\|auth.ts\|session\|login\|signup" apps/`
2. Remove auth middleware from Express routes
3. Remove login/signup/profile UI components from frontend
4. Remove auth-related env vars from `.env.example`
5. Verify backend starts without auth errors

**Verify:** Backend starts with `bun run dev` and responds to `/health`.

---

### Task 3: Strip Payments & Credits System
**Objective:** Remove Razorpay integration and credit system.

**Files to modify/remove:**
- Remove: Payment/credits routes and models
- Remove: Credit deduction logic from generation endpoints
- Remove: Pricing/plan UI components
- Modify: Generation endpoints to work without credit checks

**Steps:**
1. Find all payment/credits code: `grep -r "razorpay\|credits\|payment\|subscription" apps/`
2. Remove payment routes and models
3. Remove credit deduction from generation logic
4. Remove pricing UI pages
5. Simplify generation endpoints (no credit validation)

**Verify:** Generation endpoints work without credit checks.

---

### Task 4: Replace Postgres with SQLite
**Objective:** Simplify database to SQLite for personal use (no Docker Postgres needed).

**Files to modify:**
- Replace Prisma+Postgres with better-sqlite3 or Drizzle+SQLite
- Simplify schema to: videos, images, templates, avatars (no users table)
- Remove Prisma schema and migrations

**Steps:**
1. Remove Prisma dependency and schema
2. Install `better-sqlite3` and `drizzle-orm`
3. Create simple SQLite schema:
   ```sql
   CREATE TABLE generations (
     id INTEGER PRIMARY KEY,
     type TEXT, -- 'video', 'image', 'template'
     prompt TEXT,
     model TEXT,
     file_path TEXT,
     created_at DATETIME DEFAULT CURRENT_TIMESTAMP
   );
   CREATE TABLE avatars (
     id INTEGER PRIMARY KEY,
     name TEXT,
     file_path TEXT,
     created_at DATETIME DEFAULT CURRENT_TIMESTAMP
   );
   ```
4. Create database initialization module
5. Update all DB queries to use SQLite

**Verify:** Backend starts and can write/read from SQLite database.

---

### Task 5: Replace S3/MinIO with Local File Storage
**Objective:** Store generated media on local disk instead of S3.

**Files to modify:**
- Remove: MinIO/S3 client code
- Create: Local file storage utility
- Modify: Upload/download routes to use local paths

**Steps:**
1. Create `apps/backend/src/storage.ts`:
   ```typescript
   import fs from 'fs/promises';
   import path from 'path';
   
   const MEDIA_DIR = path.join(process.cwd(), 'media');
   
   export async function saveFile(buffer: Buffer, filename: string): Promise<string> {
     await fs.mkdir(MEDIA_DIR, { recursive: true });
     const filePath = path.join(MEDIA_DIR, filename);
     await fs.writeFile(filePath, buffer);
     return `/media/${filename}`;
   }
   
   export async function getFile(filename: string): Promise<Buffer> {
     return fs.readFile(path.join(MEDIA_DIR, filename));
   }
   ```
2. Add static file serving: `app.use('/media', express.static(path.join(process.cwd(), 'media')))`
3. Update all upload/download endpoints to use local storage
4. Remove MinIO from docker-compose.yml

**Verify:** Can upload and retrieve a file via API.

---

## Phase 2: Core Pipeline (Image + Face Swap + Video)

### Task 6: Image Generation Endpoint
**Objective:** Create endpoint that generates images from text prompts via OpenRouter.

**Files to create:**
- `apps/backend/src/routes/generate.ts`

**Steps:**
1. Create POST `/api/generate/image` endpoint
2. Accept: `{ prompt: string, model?: string, width?: number, height?: number }`
3. Call OpenRouter API with image generation model (default: flux-schnell)
4. Save generated image to local storage
5. Return: `{ id, url, prompt, model, created_at }`

**Endpoint shape:**
```typescript
router.post('/image', async (req, res) => {
  const { prompt, model = 'black-forest-labs/flux-schnell', width = 1024, height = 768 } = req.body;
  
  const response = await fetch('https://openrouter.ai/api/v1/images/generations', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${process.env.OPENROUTER_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ model, prompt, width, height })
  });
  
  const data = await response.json();
  // Save and return...
});
```

**Verify:** Can generate an image via curl and get back a URL.

---

### Task 7: Video Generation Endpoint
**Objective:** Create endpoint that generates videos from text prompts via OpenRouter.

**Files to create:**
- `apps/backend/src/routes/generate-video.ts`

**Steps:**
1. Create POST `/api/generate/video` endpoint
2. Accept: `{ prompt: string, model?: string, duration?: number, start_frame?: string, end_frame?: string }`
3. Call OpenRouter API with video generation model (default: minimax-video-01)
4. Handle async generation (poll for completion)
5. Save completed video to local storage
6. Return: `{ id, url, prompt, model, duration, created_at }`

**Note:** Video generation is async — may take 30s-2min. Implement polling or webhook pattern.

**Verify:** Can generate a video via curl and get back a URL.

---

### Task 8: Face Swap Integration
**Objective:** Integrate FaceFusion for face swapping.

**Files to create:**
- `apps/backend/src/routes/face-swap.ts`
- `docker-compose.facefusion.yml` (separate compose for FaceFusion)

**Steps:**
1. Create FaceFusion Docker compose file:
   ```yaml
   services:
     facefusion:
       image: facefusion/facefusion:latest
       ports:
         - "7865:7865"
       volumes:
         - ./media:/media
       profiles:
         - facefusion
   ```
2. Create POST `/api/face-swap` endpoint
3. Accept: `{ image_path: string, avatar_path: string }`
4. Call FaceFusion API at `http://localhost:7865/swap`
5. Save swapped image to local storage
6. Return: `{ id, url, original, avatar, created_at }`

**Verify:** Can swap faces between two images via curl.

---

### Task 9: Simplified Template System
**Objective:** Create a simplified template system for reusable video sequences.

**Files to create:**
- `apps/backend/src/routes/templates.ts`
- `apps/frontend/src/components/TemplateEditor.tsx` (simplified)

**Steps:**
1. Create template data model:
   ```typescript
   interface Template {
     id: number;
     name: string;
     segments: TemplateSegment[];
     created_at: string;
   }
   
   interface TemplateSegment {
     order: number;
     prompt: string;
     duration: number;
     start_frame?: string;
     end_frame?: string;
     face_swap: boolean;
   }
   ```
2. Create CRUD endpoints: GET/POST/PUT/DELETE `/api/templates`
3. Create simplified template editor UI (no Premiere Pro complexity)
4. Template editor: add segments, set prompts, toggle face swap per segment

**Verify:** Can create, list, and use a template.

---

## Phase 3: Frontend UI

### Task 10: Simplified Landing/Dashboard
**Objective:** Create a clean dashboard showing recent generations.

**Files to create:**
- `apps/frontend/src/pages/Dashboard.tsx`

**Steps:**
1. Create dashboard with three sections:
   - Recent Images (grid of generated images)
   - Recent Videos (grid of generated videos)
   - Templates (list of saved templates)
2. Click on any item to view full-size
3. "Generate New" buttons for each type

**Verify:** Dashboard loads and displays generations.

---

### Task 11: Generation UI
**Objective:** Create clean generation interfaces for images, videos, and face swap.

**Files to create:**
- `apps/frontend/src/pages/GenerateImage.tsx`
- `apps/frontend/src/pages/GenerateVideo.tsx`
- `apps/frontend/src/pages/FaceSwap.tsx`

**Steps:**
1. Image generation page:
   - Text prompt input (large textarea)
   - Model dropdown (flux-schnell, flux-dev, sd-xl)
   - Resolution selector
   - Generate button
   - Loading state + result preview

2. Video generation page:
   - Text prompt input
   - Model dropdown (minimax-video-01, kling, etc.)
   - Duration selector (5s, 10s, 15s)
   - Optional: start frame upload, end frame upload
   - Generate button
   - Progress indicator (polling status)

3. Face swap page:
   - Upload base image
   - Upload/select avatar
   - Generate button
   - Result preview

**Verify:** Can generate images, videos, and swap faces via UI.

---

### Task 12: Navigation & Routing
**Objective:** Wire up React Router for page navigation.

**Files to modify:**
- `apps/frontend/src/App.tsx`

**Steps:**
1. Add React Router with routes:
   - `/` → Dashboard
   - `/generate/image` → Image generation
   - `/generate/video` → Video generation
   - `/face-swap` → Face swap
   - `/templates` → Template list
   - `/templates/:id` → Template editor
2. Add simple sidebar navigation
3. Style with Tailwind (dark theme, clean UI)

**Verify:** Can navigate between all pages.

---

## Phase 4: Polish & Testing

### Task 13: Environment Configuration
**Objective:** Create clean .env setup for local development.

**Files to create:**
- `apps/backend/.env.example`
- `apps/frontend/.env.example`

**Steps:**
1. Backend env:
   ```
   OPENROUTER_API_KEY=your-key-here
   FACEFUSION_URL=http://localhost:7865
   MEDIA_DIR=./media
   PORT=4000
   ```

2. Frontend env:
   ```
   VITE_API_URL=http://localhost:4000
   ```

3. Update docker-compose.yml to only include backend + frontend (remove Postgres, MinIO)

**Verify:** App starts with fresh `.env` files.

---

### Task 14: Build & Test
**Objective:** Verify everything works end-to-end.

**Steps:**
1. Run `bun run build` — must pass
2. Start backend: `cd apps/backend && bun run dev`
3. Start frontend: `cd apps/frontend && bun run dev`
4. Test image generation (requires OPENROUTER_API_KEY)
5. Test video generation (requires OPENROUTER_API_KEY)
6. Test face swap (requires FaceFusion running)
7. Test template creation and usage

**Verify:** All features work end-to-end.

---

## Success Criteria

- [ ] Can generate images from text prompts
- [ ] Can generate videos from text prompts
- [ ] Can swap faces between images
- [ ] Can create and use templates
- [ ] No auth/payments/credits (personal tool)
- [ ] Local file storage (no S3)
- [ ] SQLite database (no Postgres)
- [ ] Clean, usable UI
- [ ] Runs locally with `bun run dev`

---

## Notes for Codex

1. **This is a personal tool** — no SaaS features, no user management
2. **Keep it simple** — YAGNI, don't over-engineer
3. **OpenRouter is the main API** — video gen, image gen all go through OpenRouter
4. **FaceFusion is self-hosted** — Docker compose for face swap
5. **Local storage is fine** — no need for S3/MinIO for personal use
6. **Dark theme preferred** — use the Tripp design system colors if possible:
   - Background: #0a0a0a
   - Sidebar: #121212
   - Accent: #39FF14 (lime green)
   - Text: #ffffff

---

## What Eddie Will Handle Later

1. **OpenRouter API key** — Eddie will provide and configure
2. **Video gen model selection** — Eddie will choose which OpenRouter models to use
3. **FaceFusion setup** — Eddie will run Docker compose for face swap
4. **Content creation** — Eddie will use the tool to make videos

---

*Plan written: 2026-07-17*
*Estimated effort: 2-3 days with Codex*
