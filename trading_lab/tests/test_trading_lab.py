import unittest

from trading_lab.broker import BrokerClient, GuardedBrokerClient
from trading_lab.engine import TradingEngine
from trading_lab.models import OrderProposal, OrderType, RiskLimits, Side, TradeSignal, TradingMode
from trading_lab.order_gate import ConfirmationGate
from trading_lab.paper import PaperBroker
from trading_lab.risk import RiskManager


class DummyBroker(BrokerClient):
    def get_holdings(self):
        return {"success": True}

    def get_positions(self):
        return {"success": True}

    def place_order(self, order):
        return {"success": True, "placed": True, "symbol": order.symbol}


class TradingLabTests(unittest.TestCase):
    def test_risk_blocks_market_order_by_default(self):
        limits = RiskLimits(10000, 100, 300, 2)
        order = OrderProposal.create("TCS", Side.BUY, 1, OrderType.MARKET, None, 3900, 4000, 50, "test")

        result = RiskManager(limits).validate_order(order)

        self.assertFalse(result["allowed"])

    def test_guarded_broker_requires_confirmation(self):
        order = OrderProposal.create("TCS", Side.BUY, 1, OrderType.LIMIT, 3920, 3880, 3990, 40, "test")

        result = GuardedBrokerClient(DummyBroker()).place_order(order)

        self.assertFalse(result["success"])

    def test_guarded_live_places_only_confirmed_order(self):
        limits = RiskLimits(10000, 100, 300, 2)
        engine = TradingEngine(TradingMode.LIVE_TRADING_GUARDED, limits, broker=DummyBroker())
        signal = TradeSignal("TCS", Side.BUY, 0.8, "test", 3920, 3880, 3990)

        preview = engine.handle_signal(signal, quantity=1)
        preview_id = preview["proposal"].preview_id
        blocked = engine.confirm_order(preview_id, "CONFIRM WRONG")
        placed = engine.confirm_order(preview_id, preview["confirmation_phrase"])

        self.assertFalse(blocked["success"])
        self.assertTrue(placed["success"])
        self.assertTrue(placed["placed"])

    def test_research_mode_returns_proposal_only(self):
        limits = RiskLimits(10000, 100, 300, 2)
        engine = TradingEngine(TradingMode.RESEARCH_ONLY, limits)
        signal = TradeSignal("INFY", Side.BUY, 0.7, "test", 1500, 1480, 1540)

        result = engine.handle_signal(signal, quantity=1)

        self.assertTrue(result["success"])
        self.assertEqual(result["stage"], "research")

    def test_confirmation_gate_requires_exact_phrase(self):
        order = OrderProposal.create("INFY", Side.BUY, 1, OrderType.LIMIT, 1500, 1480, 1540, 20, "test")
        gate = ConfirmationGate()
        preview = gate.preview(order)

        rejected = gate.confirm(order.preview_id, "yes")
        accepted = gate.confirm(order.preview_id, preview["confirmation_phrase"])

        self.assertFalse(rejected["success"])
        self.assertTrue(accepted["success"])

    def test_paper_broker_updates_cash_and_position_in_memory(self):
        broker = PaperBroker(10000)
        order = OrderProposal.create("INFY", Side.BUY, 2, OrderType.LIMIT, 1500, 1480, 1540, 40, "test")

        result = broker.place_order(order)

        self.assertTrue(result["success"])
        self.assertEqual(result["cash"], 7000)
        self.assertIn("INFY", broker.positions)


if __name__ == "__main__":
    unittest.main()
