import { decrementQuantity, incrementQuantity } from '../utils/quantity';

export function QuantityControl({
  value,
  minimum,
  step,
  onChange,
  disabled = false,
}: {
  value: number;
  minimum: number;
  step: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="quantity-control" aria-label="Количество">
      <button
        type="button"
        aria-label="Уменьшить количество"
        disabled={disabled || value <= minimum}
        onClick={() => onChange(decrementQuantity(value, minimum, step))}
      >
        −
      </button>
      <output aria-live="polite">{value}</output>
      <button
        type="button"
        aria-label="Увеличить количество"
        disabled={disabled}
        onClick={() => onChange(incrementQuantity(value, minimum, step))}
      >
        +
      </button>
    </div>
  );
}
