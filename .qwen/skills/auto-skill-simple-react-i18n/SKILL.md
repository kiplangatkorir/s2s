---
name: simple-react-i18n
description: Lightweight bilingual support for React apps using Context API without external i18n libraries
source: auto-skill
extracted_at: '2026-06-19T17:18:28.562Z'
---

# Simple React Bilingual i18n with Context API

## When to use

When you need to add language switching (e.g., English/Swahili) to a React app and:
- You only support 2-3 languages
- You don't want to add a heavy i18n library (i18next, react-intl, etc.)
- You need a quick, type-safe solution
- Your translations are static (not loaded from API)

## Implementation

### 1. Define translations object

Create a typed translations object with all UI strings:

```typescript
// lib/i18n.ts
const translations = {
  en: {
    greeting: "Hello",
    send: "Send",
    cancel: "Cancel",
    // ... all UI strings
  },
  sw: {
    greeting: "Habari",
    send: "Tuma",
    cancel: "Ghairi",
    // ... all UI strings
  },
} as const;

type Lang = "en" | "sw";
type Translations = typeof translations.en;
```

### 2. Create Context Provider

```typescript
import { createContext, useContext, useState, ReactNode } from "react";

interface I18nContextType {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: Translations;
}

const I18nContext = createContext<I18nContextType | undefined>(undefined);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("en");
  const t = translations[lang];

  return (
    <I18nContext.Provider value={{ lang, setLang, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return context;
}
```

### 3. Wrap your app

```typescript
// app/layout.tsx or App.tsx
import { I18nProvider } from "@/lib/i18n";

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <I18nProvider>{children}</I18nProvider>
      </body>
    </html>
  );
}
```

### 4. Use in components

```typescript
import { useI18n } from "@/lib/i18n";

export function Button() {
  const { t } = useI18n();
  return <button>{t.send}</button>;
}
```

### 5. Create language toggle

```typescript
import { useI18n } from "@/lib/i18n";

export function LanguageToggle() {
  const { lang, setLang } = useI18n();

  return (
    <button
      onClick={() => setLang(lang === "en" ? "sw" : "en")}
      className="px-3 py-1 rounded border"
    >
      {lang === "en" ? "Switch to Swahili" : "Badili Kiingereza"}
    </button>
  );
}
```

## Advantages

- **Zero dependencies**: No external libraries needed
- **Type-safe**: TypeScript catches missing translations at compile time
- **Simple**: Easy to understand and maintain
- **Fast**: No runtime translation lookups or formatting
- **Small bundle**: Only adds a few KB

## Limitations

- **No pluralization**: Can't handle "1 item" vs "2 items" automatically
- **No interpolation**: Can't do `t.greeting(name)` — use template literals instead
- **No formatting**: No date/number/currency formatting
- **Static only**: Translations must be known at build time
- **Manual maintenance**: Adding a new string requires updating all language objects

## When to upgrade to a full i18n library

Consider migrating to i18next, react-intl, or similar when:
- You need to support 5+ languages
- You need pluralization rules
- You need date/number/currency formatting
- You need to load translations from an API or CMS
- You need to support user-contributed translations
- You need translation memory or machine translation integration

For those cases, the setup cost of a full library is justified. For 2-3 languages with simple UI strings, this pattern is sufficient.

## Gotchas

- **Type safety**: Always use `as const` on the translations object to preserve literal types
- **Missing translations**: TypeScript will catch missing keys, but runtime access to undefined keys returns `undefined`
- **HTML content**: Don't use `dangerouslySetInnerHTML` with translations — escape or sanitize first
- **Persistence**: Add `localStorage` to remember user's language preference:
  ```typescript
  const [lang, setLang] = useState<Lang>(() => {
    return (localStorage.getItem("lang") as Lang) || "en";
  });
  
  useEffect(() => {
    localStorage.setItem("lang", lang);
  }, [lang]);
  ```
