import { describe, expect, it } from 'vitest';
import { decrementQuantity, incrementQuantity, isValidQuantity, normalizeQuantity } from './quantity';

describe('правила количества', () => {
  it('начинает с минимальной партии и двигается по шагу', () => {
    expect(incrementQuantity(5, 5, 2.5)).toBe(7.5);
    expect(decrementQuantity(7.5, 5, 2.5)).toBe(5);
    expect(decrementQuantity(5, 5, 2.5)).toBe(5);
  });

  it('поддерживает дробный шаг без накопления float-ошибки', () => {
    expect(incrementQuantity(0.3, 0.3, 0.1)).toBe(0.4);
    expect(incrementQuantity(0.4, 0.3, 0.1)).toBe(0.5);
    expect(isValidQuantity(0.5, 0.3, 0.1)).toBe(true);
  });

  it('отклоняет значение между шагами и ниже минимума', () => {
    expect(isValidQuantity(4, 5, 1)).toBe(false);
    expect(isValidQuantity(6, 5, 2)).toBe(false);
    expect(isValidQuantity(7, 5, 2)).toBe(true);
  });

  it('нормализует произвольный ввод к ближайшему шагу', () => {
    expect(normalizeQuantity(8.1, 5, 2)).toBe(9);
    expect(normalizeQuantity(5.2, 5, 2)).toBe(5);
  });

  it('не принимает нулевой или отрицательный шаг', () => {
    expect(() => normalizeQuantity(1, 1, 0)).toThrow('Некорректные правила количества');
    expect(isValidQuantity(1, 1, -1)).toBe(false);
  });
});
