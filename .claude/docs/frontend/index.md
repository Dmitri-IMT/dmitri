# frontend

The React 19 + TypeScript SPA (Vite). This feature (spec 014 / roadmap T9) is the greenfield
*scaffold* only: contract-typed API access and the full auth-client plumbing, with a throwaway
stub UI. Source lives at `frontend/src/`.

## Overview

* [Package overview](./overview.md) — The React 19 + TypeScript SPA scaffold — contract-typed API access and the auth-client plumbing, with only a throwaway stub UI.

## API layer

* [api](./api.md) — The two Axios instances, the single-flight 401→refresh interceptor, the auth resource module, and the in-memory token store.

## App root & stub UI

* [app](./app.md) — The React root, the boot-time silent-refresh gate, and the throwaway login stub + signed-in placeholder.
