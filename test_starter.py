import asyncio
import unittest
from decimal import Decimal as D

from starter import recommend_price, sample_fetch_offers


class PriceTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_calculation(self):
        result = await recommend_price(sample_fetch_offers, D("4900.00"), D("4500.00"))
        self.assertEqual(result["price"], D("4728.00"))
        self.assertEqual(result["decision"], "APPLY")
        self.assertIsInstance(result["price"], D)

    async def test_source_error_partial_and_timeout_keep_current(self):
        async def error():
            raise OSError("source unavailable")

        async def partial():
            return {"status": "partial", "offers": []}

        async def slow():
            await asyncio.sleep(60)

        for fetch in (error, partial, slow):
            with self.subTest(source=fetch.__name__):
                result = await recommend_price(fetch, D("90.00"), D("100.00"), timeout_s=.01)
                self.assertEqual(result["price"], D("90.00"))
                self.assertEqual(result["decision"], "HOLD")

    async def test_no_eligible_offers_does_not_apply_floor(self):
        async def fetch():
            return {"status": "success", "offers": [
                {"seller": "MyShOp", "price": D("1.00"), "delivery_days": 0},
                {"seller": "unknown", "price": D("1.00"), "delivery_days": None},
                {"seller": "slow", "price": D("1.00"), "delivery_days": 7},
            ]}
        result = await recommend_price(fetch, D("90.00"), D("100.00"))
        self.assertEqual((result["price"], result["decision"]), (D("90.00"), "HOLD"))

    async def calculate(self, competitor, current, floor):
        async def fetch():
            return {"status": "success", "offers": [
                {"seller": "other", "price": D(competitor), "delivery_days": 6},
            ]}
        return await recommend_price(fetch, D(current), D(floor))

    async def test_round_down_and_minimum_price(self):
        result = await self.calculate("100.01", "100.00", "1.00")
        self.assertEqual(result["price"], D("98.50"))
        result = await self.calculate("100.01", "100.00", "99.00")
        self.assertEqual(result["price"], D("99.00"))

    async def test_exact_thirty_percent_allowed_both_directions(self):
        for competitor, floor, expected in [("100.00", "130.00", "130.00"),
                                              ("71.07", "1.00", "70.00")]:
            result = await self.calculate(competitor, "100.00", floor)
            self.assertEqual(result["price"], D(expected))
            self.assertEqual(result["decision"], "APPLY")

    async def test_over_thirty_percent_requires_review_both_directions(self):
        for competitor, floor in [("100.00", "130.01"), ("71.06", "1.00")]:
            result = await self.calculate(competitor, "100.00", floor)
            self.assertEqual(result["decision"], "REVIEW")

    async def test_cancellation_is_propagated(self):
        async def cancelled():
            raise asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await recommend_price(cancelled, D("100.00"), D("1.00"))


if __name__ == "__main__":
    unittest.main()
