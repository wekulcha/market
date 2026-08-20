import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react';

export function Card({ children, className = '', ...props }: HTMLAttributes<HTMLElement> & { children: ReactNode }) {
  return <section {...props} className={`card ${className}`.trim()}>{children}</section>;
}

export function Button({
  variant = 'primary',
  size = 'md',
  busy = false,
  children,
  className = '',
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md';
  busy?: boolean;
}) {
  return (
    <button
      {...props}
      className={`button button--${variant} button--${size} ${className}`.trim()}
      disabled={disabled || busy}
    >
      {busy && <span className="button__spinner" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode;
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info';
}) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="page-header__description">{description}</p>}
      </div>
      {action && <div className="page-header__action">{action}</div>}
    </header>
  );
}

export function Field({
  label,
  hint,
  error,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string; error?: string }) {
  const id = props.id ?? `field-${props.name ?? label.toLowerCase().replace(/\s+/g, '-')}`;
  return (
    <label className="field" htmlFor={id}>
      <span className="field__label">{label}</span>
      <input {...props} id={id} className="field__control" />
      {hint && !error && <span className="field__hint">{hint}</span>}
      {error && <span className="field__error">{error}</span>}
    </label>
  );
}

export function SelectField({
  label,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string; children: ReactNode }) {
  const id = props.id ?? `field-${props.name ?? label.toLowerCase().replace(/\s+/g, '-')}`;
  return (
    <label className="field" htmlFor={id}>
      <span className="field__label">{label}</span>
      <select {...props} id={id} className="field__control">{children}</select>
    </label>
  );
}

export function TextAreaField({
  label,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  const id = props.id ?? `field-${props.name ?? label.toLowerCase().replace(/\s+/g, '-')}`;
  return (
    <label className="field" htmlFor={id}>
      <span className="field__label">{label}</span>
      <textarea {...props} id={id} className="field__control field__control--textarea" />
    </label>
  );
}

export function Notice({
  children,
  tone = 'info',
}: {
  children: ReactNode;
  tone?: 'info' | 'success' | 'warning' | 'danger';
}) {
  return <div className={`notice notice--${tone}`} role={tone === 'danger' ? 'alert' : undefined}>{children}</div>;
}

export function StatePanel({
  title,
  description,
  icon = '○',
  action,
}: {
  title: string;
  description?: string;
  icon?: string;
  action?: ReactNode;
}) {
  return (
    <div className="state-panel">
      <span className="state-panel__icon" aria-hidden="true">{icon}</span>
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}

export function LoadingPanel({ label = 'Загружаем данные…' }: { label?: string }) {
  return (
    <div className="loading-panel" role="status">
      <span className="loading-panel__spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function SkeletonCards({ count = 3 }: { count?: number }) {
  return (
    <div className="skeleton-grid" aria-label="Загрузка">
      {Array.from({ length: count }, (_, index) => <div className="skeleton-card" key={index} />)}
    </div>
  );
}

export function Metric({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <Card className="metric">
      <span className="metric__label">{label}</span>
      <strong className="metric__value">{value}</strong>
      {hint && <span className="metric__hint">{hint}</span>}
    </Card>
  );
}
