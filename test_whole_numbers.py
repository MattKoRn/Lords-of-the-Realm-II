import unittest

import whole_numbers


class WholeNumberFormattingTests(unittest.TestCase):
    def test_plain_decimal_rounds(self):
        self.assertEqual(whole_numbers.whole_number_text('Value 10.6'), 'Value 11')

    def test_signed_decimal_rounds(self):
        self.assertEqual(whole_numbers.whole_number_text('Forecast +0.03'), 'Forecast +0')

    def test_seconds_round(self):
        self.assertEqual(whole_numbers.whole_number_text('Next 24.6s'), 'Next 25s')

    def test_percent_rounds(self):
        self.assertEqual(whole_numbers.whole_number_text('Confidence 87.5%'), 'Confidence 88%')

    def test_suffix_is_preserved(self):
        self.assertEqual(whole_numbers.whole_number_text('Gold 1.7K'), 'Gold 2K')


if __name__ == '__main__':
    unittest.main()
