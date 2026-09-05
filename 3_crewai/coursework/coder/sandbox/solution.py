from decimal import Decimal, getcontext


def main() -> None:
    # Use high precision to reduce floating-point error.
    getcontext().prec = 60

    n_terms = 100_000
    total = Decimal(0)

    # Terms are: 1 - 1/3 + 1/5 - 1/7 + ...
    # Term k (0-indexed) has denominator (2*k + 1) and sign (-1)^k.
    for k in range(n_terms):
        denom = Decimal(2 * k + 1)
        term = Decimal(1) / denom
        if k % 2 == 0:
            total += term
        else:
            total -= term

    result = total * Decimal(4)

    # Print both the raw sum and the final multiplied value.
    print(f"sum={total}")
    print(f"4*sum={result}")


if __name__ == "__main__":
    main()
