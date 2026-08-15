"""
UK VAT number checksum validation.

A UK VAT number has 9 digits.
The first 7 digits are the "body",the last 2 are "check digits".
The check digits are calculated from the body, so a random 9-digit number is almost never a real VAT number.
This means we can throw away most bad candidates for free,without asking HMRC anything."""

WEIGHTS = [8, 7, 6, 5, 4, 3, 2]


def keep_only_digits(text):
    """Turn 'GB 123 4567 82' into '123456782'. """
    result = ""
    for character in text:
        if character.isdigit():
            result = result + character
    return result


def is_valid_vat(number):
    """Return True if the number passes the UK VAT checksum"""
    digits = keep_only_digits(number)

    if len(digits) != 9:
        return False

    total = 0
    for position in range(7):
        digit = int(digits[position])
        total = total + digit * WEIGHTS[position]

    check_digits = int(digits[7] + digits[8])
    total = total + check_digits

    if total % 97 == 0:
        return True
    if (total + 55) % 97 == 0:
        return True

    return False


def make_valid_vat(first_7_digits):
    """Given 7 digits, work out the 2 check digits that make it valid.
    We only use this to create test data. These are NOT real companies' numbers, they are just numbers where the math works out.
    """
    total = 0
    for position in range(7):
        digit = int(first_7_digits[position])
        total = total + digit * WEIGHTS[position]

    check_digits = 97 - (total % 97)
    check_as_text = str(check_digits).zfill(2)

    return first_7_digits + check_as_text


if __name__ == "__main__":
    print("---numbers built to satisfy the checksum---")
    for prefix in ["1234567", "9876543", "5550001"]:
        vat = make_valid_vat(prefix)
        print("  " + prefix + " -> GB" + vat + "   valid? " + str(is_valid_vat(vat)))
    print("")
    print("---numbers that look plausible but are not valid--")

    for junk in ["123456789", "111111111", "987654321", "202400001"]:
        print("  GB" + junk + "   valid? " + str(is_valid_vat(junk)))
    print("")
    print("---how much rubbish does the checksum remove?---")
    tested = 0
    passed = 0

    for number in range(100000000, 100100000):
        tested = tested + 1
        if is_valid_vat(str(number)):
            passed = passed + 1

    print("  tested: " + str(tested) + " numbers")
    print("  passed: " + str(passed) + " numbers")
    print("  so the checksum removes about " + str(round(100 - passed / tested * 100, 1)) + "% for free")
