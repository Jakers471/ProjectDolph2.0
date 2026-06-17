 API
Endpoint /api/trades
78 positions, 301 total trades
Endpoint /api/equity
209 equity snapshots
Endpoint /api/signals
500 parsed signals
Endpoint /api/config
min_confidence=0.6 max_positions=10
starting_balance
$7000
final_balance (equity[-1])
$10455.68
total_pnl (final - start)
+$3455.6789
P&L FORMULA APPLIED PER TRADE
Formula
notional × close_fraction × (exit_price − entry_price) / entry_price × side_mult
TRIM close_fraction
0.50 (closes 50% of remaining notional)
EXIT close_fraction
1.00 (closes 100% of remaining notional)
BUY / ADD trade_pnl
0.00 (no realized P&L on opening a position)
Exit price fallback
If signal has no parsed price → uses position entry_price → $0 break-even
positions.realized_pnl
Cumulative sum of all trade_pnl within that position
ZERO / ANOMALY DIAGNOSTICS
Zero-PnL SELL trades
62 trades — exit price fell back to entry (no price parsed)
Trade#7008 (2024-02-01)
price=2.6 qty=125 → PnL=$0 (break-even fallback)
Trade#7035 (2024-03-05)
price=1.1 qty=500 → PnL=$0 (break-even fallback)
Trade#7014 (2024-02-02)
price=0.87 qty=250 → PnL=$0 (break-even fallback)
Trade#7015 (2024-02-05)
price=0.87 qty=250 → PnL=$0 (break-even fallback)
Trade#7296 (2026-06-17)
price=0.55 qty=500 → PnL=$0 (break-even fallback)
Trade#7023 (2024-02-20)
price=0.55 qty=500 → PnL=$0 (break-even fallback)
High-magnitude trades (|PnL|>$500)
2 trades — likely parser price mismatch
Trade#7011 SELL
price=1.9 pnl=+$805.56
Trade#7018 SELL
price=1.45 pnl=+$1111.11
POSITION SIZE TRACKING
Pos#1621 MARA [closed]
BUY→100% SELL→50% SELL→25% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1622 BTC [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1623 MARA [closed]
BUY→100% SELL→50% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1624 MARA [closed]
BUY→100% SELL→50% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1625 TSLA [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1626 CLSK [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1627 MARA [closed]
SELL_SHORT→100% BUY_COVER→50% BUY_COVER→0% | remaining=0% ($$0 of $$500)
Pos#1628 HOOD [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1629 BEAT [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1630 CLSK [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1631 CLSK [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1632 MARA [closed]
BUY→100% SELL→50% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1633 CLSK [closed]
SELL_SHORT→100% BUY_COVER→0% | remaining=0% ($$0 of $$500)
Pos#1634 CLSK [closed]
BUY→100% ADD→100% SELL→50% SELL→25% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1635 ORDI [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1636 NVDA [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1637 AVAX [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1638 INJ [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1639 BNB [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→6% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1640 BTC [closed]
BUY→100% SELL→50% SELL→25% ADD→25% SELL→12% SELL→6% SELL→3% SELL→2% SELL→1% SELL→0% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1641 SOL [closed]
BUY→100% SELL→50% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1642 ETH [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1643 ETH [closed]
BUY→100% SELL→50% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1644 MARA [closed]
BUY→100% SELL→50% SELL→25% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1645 USDT [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1646 ENS [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1647 MARA [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→6% SELL→3% SELL→2% SELL→1% SELL→0% SELL→0% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1648 MARA [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→6% SELL→3% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1649 ONDO [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1650 BTC [closed]
BUY→100% SELL→50% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1651 MARA [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1652 MARA [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→6% SELL→3% SELL→2% SELL→1% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1653 MARA [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→6% SELL→3% SELL→2% SELL→1% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1654 HOOD [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1655 LINK [closed]
BUY→100% SELL→50% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1656 MARA [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→6% SELL→3% SELL→2% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1657 BTC [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1658 MARA [closed]
SELL_SHORT→100% BUY_COVER→50% BUY_COVER→25% BUY_COVER→12% BUY_COVER→0% | remaining=0% ($$0 of $$500)
Pos#1659 ENA [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→6% SELL→3% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1660 HOOD [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→6% SELL→3% SELL→2% SELL→1% SELL→0% SELL→0% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1661 MARA [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1662 MARA [closed]
BUY→100% SELL→50% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1663 ETH [closed]
BUY→100% SELL→50% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1664 MARA [closed]
SELL_SHORT→100% BUY_COVER→50% BUY_COVER→0% | remaining=0% ($$0 of $$500)
Pos#1665 BTC [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1666 MARA [closed]
SELL_SHORT→100% BUY_COVER→0% | remaining=0% ($$0 of $$500)
Pos#1667 MARA [closed]
BUY→100% SELL→50% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1668 MARA [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1669 HOOD [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1670 MARA [closed]
SELL_SHORT→100% BUY_COVER→50% BUY_COVER→25% BUY_COVER→12% BUY_COVER→6% BUY_COVER→0% | remaining=0% ($$0 of $$500)
Pos#1671 ETH [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→6% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1672 ETH [closed]
BUY→100% SELL→50% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1673 MARA [closed]
SELL_SHORT→100% BUY_COVER→50% BUY_COVER→25% BUY_COVER→12% BUY_COVER→6% BUY_COVER→3% BUY_COVER→0% | remaining=0% ($$0 of $$500)
Pos#1674 ETH [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→6% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1675 SUI [closed]
BUY→100% SELL→50% SELL→25% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1676 SOL [closed]
BUY→100% SELL→50% SELL→25% ADD→25% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1677 BTC [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→6% SELL→3% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1678 BTC [closed]
BUY→100% SELL→50% SELL→25% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1679 TAO [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1680 TAO [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1681 TAO [closed]
BUY→100% SELL→50% SELL→25% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1682 ETH [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1683 ETH [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1684 BTC [closed]
SELL_SHORT→100% BUY_COVER→0% | remaining=0% ($$0 of $$500)
Pos#1685 BTC [closed]
SELL_SHORT→100% BUY_COVER→0% | remaining=0% ($$0 of $$500)
Pos#1686 BTC [closed]
SELL_SHORT→100% BUY_COVER→0% | remaining=0% ($$0 of $$500)
Pos#1687 IBIT [closed]
BUY→100% SELL→50% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1688 BMNR [closed]
SELL_SHORT→100% BUY_COVER→50% BUY_COVER→25% BUY_COVER→12% BUY_COVER→6% BUY_COVER→0% | remaining=0% ($$0 of $$500)
Pos#1689 IBIT [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1690 IBIT [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→6% SELL→3% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1691 BTC [closed]
SELL_SHORT→100% BUY_COVER→0% | remaining=0% ($$0 of $$500)
Pos#1692 IBIT [closed]
BUY→100% SELL→50% SELL→25% SELL→12% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1693 BTC [closed]
BUY→100% ADD→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1694 IBIT [closed]
BUY→100% SELL→50% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1695 IBIT [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1696 BTC [closed]
BUY→100% SELL→50% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1697 HYPE [closed]
BUY→100% SELL→0% | remaining=0% ($$0 of $$500)
Pos#1698 DOGE [closed]
BUY→100% SELL→50% SELL→25% SELL→0% | remaining=0% ($$0 of $$500)
RAW CONFIG (/api/config)
{
  "_comment": "Grizzlies — last saved 2026-06-17T19:14:00Z",
  "risk": {
    "min_confidence": 0.6,
    "max_open_positions": 10,
    "kill_switch": false,
    "allowed_asset_types": [
      "CRYPTO",
      "OPTION"
    ],
    "allowed_actions": [
      "ENTRY",
      "TRIM",
      "EXIT",
      "ADD"
    ]
  },
  "parser": {
    "corpus_path": "data/{trader}/messages.jsonl",
    "signals_path": "data/{trader}/signals/",
    "active": true
  },
  "broker": {
    "dry_run": true,
    "trade_notional": 500,
    "trim_fraction": 0.5,
    "starting_balance": 7000,
    "default_quantity": 1,
    "add_quantity": 0.5
  }
}
RAW EQUITY EVENTS (last 5)
2026-04-29 IBIT
trade_pnl=+$0.0000 balance=$$10455.01
2026-04-29 BTC
trade_pnl=$-0.1470 balance=$$10454.86
2026-04-30 BTC
trade_pnl=+$0.8182 balance=$$10455.68
2026-05-03 DOGE
trade_pnl=+$0.0000 balance=$$10455.68
2026-05-03 DOGE
trade_pnl=+$0.0000 balance=$$10455.68
RAW POSITIONS JSON (first 3)
[
  {
    "position_id": 1621,
    "symbol": "MARA",
    "asset_type": "OPTION",
    "side": "LONG",
    "entry_price": 2.6,
    "original_qty": 500,
    "remaining": 0,
    "remaining_pct": 0,
    "opened_at": "2024-01-02T12:57:08.687-06:00",
    "closed_at": "2024-02-01T09:42:00.661-06:00",
    "final_exit": null,
    "total_pnl": 125.9615,
    "status": "closed",
    "trades": [
      {
        "trade_id": 7005,
        "time": "2024-01-02T12:57:08.687-06:00",
        "action": "BUY",
        "price": 2.6,
        "quantity": 500,
        "close_fraction": 0,
        "trade_pnl": 0,
        "trade_status": "filled",
        "dry_run": true,
        "size_after_pct": 100
      },
      {
        "trade_id": 7006,
        "time": "2024-01-04T13:26:52.594-06:00",
        "action": "SELL",
        "price": 3,
        "quantity": 250,
        "close_fraction": 0.5,
        "trade_pnl": 38.4615,
        "trade_status": "filled",
        "dry_run": true,
        "size_after_pct": 50
      },
      {
        "trade_id": 7007,
        "time": "2024-01-08T12:37:07.246-06:00",
        "action": "SELL",
        "price": 4.42,
        "quantity": 125,
        "close_fraction": 0.5,
        "trade_pnl": 87.5,
        "trade_status": "filled",
        "dry_run": true,
        "size_after_pct": 25
      },
      {
        "trade_id": 7008,
        "time": "2024-02-01T09:42:00.661-06:00",
        "action": "SELL",
        "price": 2.6,
        "quantity": 125,
        "close_fraction": 1,
        "trade_pnl": 0,
        "trade_status": "filled",
        "dry_run": true,
        "size_after_pct": 0
      }
    ],
    "concurrent_symbols": []
  },
  {
    "position_id": 1622,
    "symbol": "BTC",
    "asset_type": "CRYPTO",
    "side": "LONG",
    "entry_price": 1.1,
    "original_qty": 500,
    "remaining": 0,
    "remaining_pct": 0,
    "opened_at": "2024-02-01T10:58:37.709-06:00",
    "closed_at": "2024-03-05T14:02:16.899-06:00",
    "final_exit": null,
    "total_pnl": 0,
    "status": "closed",
    "trades": [
      {
        "trade_id": 7009,
        "time": "2024-02-01T10:58:37.709-06:00",
        "action": "BUY",
        "price": 1.1,
        "quantity": 500,
        "close_fraction": 0,
        "trade_pnl": 0,
        "trade_status": "filled",
        "dry_run": true,
        "size_after_pct": 100
      },
      {
        "trade_id": 7035,
        "time": "2024-03-05T14:02:16.899-06:00",
        "action": "SELL",
        "price": 1.1,
        "quantity": 500,
        "close_fraction": 1,
        "trade_pnl": 0,
        "trade_status": "filled",
        "dry_run": true,
        "size_after_pct": 0
      }
    ],
    "concurrent_symbols": [
      "MARA",
      "TSLA",
      "CLSK",
      "HOOD",
      "BEAT"
    ]
  },
  {
    "position_id": 1623,
    "symbol": "MARA",
    "asset_type": "OPTION",
    "side": "LONG",
    "entry_price": 0.45,
    "original_qty": 500,
    "remaining": 0,
    "remaining_pct": 0,
    "opened_at": "2024-02-01T11:04:03.207-06:00",
    "closed_at": "2024-02-01T11:35:55.646-06:00",
    "final_exit": null,
    "total_pnl": 1055.5556,
    "status": "closed",
    "trades": [
      {
        "trade_id": 7010,
        "time": "2024-02-01T11:04:03.207-06:00",
        "action": "BUY",
        "price": 0.45,
        "quantity": 500,
        "close_fraction": 0,
        "trade_pnl": 0,
        "trade_status": "filled",
        "dry_run": true,
        "size_after_pct": 100
      },
      {
        "trade_id": 7011,
        "time": "2024-02-01T11:31:31.929-06:00",
        "action": "SELL",
        "price": 1.9,
        "quantity": 250,
        "close_fraction": 0.5,
        "trade_pnl": 805.5556,
        "trade_status": "filled",
        "dry_run": true,
        "size_after_pct": 50
      },
      {
        "trade_id": 7012,
        "time": "2024-02-01T11:35:55.646-06:00",
        "action": "SELL",
        "price": 0.9,
        "quantity": 250,
        "close_fraction": 1,
        "trade_pnl": 250,
        "trade_status": "filled",
        "dry_run": true,
        "size_after_pct": 0
      }
    ],
    "concurrent_symbols": [
      "BTC"
    ]
  }
]
Running paper pipeline for Grizzlies...
Parsed:   7193 signals
Approved: 485
Rejected: 6708
Traded:   291

Top reject reasons:
  2490x  action=NOISE is not actionable
  1172x  action=UNSURE is not actionable
  1052x  max open positions (10) reached for Grizzlies
  622x  confidence 0.55 < min_confidence 0.6 for Grizzlies
  213x  no open position to TRIM: Grizzlies HOOD

Equity: 209 closed trades  P&L=+3455.68  balance=$$10455.68

--- Trade Log (301 events) ---
[DRY-RUN] BUY  MARA   notional=$500  @2.6  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$250  @3.0  analyst=Grizzlies  pnl=+38.4615 (+15.38%)
[DRY-RUN] SELL MARA   notional=$125  @4.42  analyst=Grizzlies  pnl=+87.5000 (+70.00%)
[DRY-RUN] SELL MARA   notional=$125  @2.6  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  BTC    notional=$500  @1.1  analyst=Grizzlies
[DRY-RUN] BUY  MARA   notional=$500  @0.45  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$250  @1.9  analyst=Grizzlies  pnl=+805.5556 (+322.22%)
[DRY-RUN] SELL MARA   notional=$250  @0.9  analyst=Grizzlies  pnl=+250.0000 (+100.00%)
[DRY-RUN] BUY  MARA   notional=$500  @0.87  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$250  @0.87  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL MARA   notional=$250  @0.87  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  TSLA   notional=$500  @0.55  analyst=Grizzlies
[DRY-RUN] BUY  CLSK   notional=$500  @0.45  analyst=Grizzlies
[DRY-RUN] SELL CLSK   notional=$500  @1.45  analyst=Grizzlies  pnl=+1111.1111 (+222.22%)
[DRY-RUN] SELL_SHORT MARA   notional=$500  @1.1  analyst=Grizzlies
[DRY-RUN] BUY  HOOD   notional=$500  @0.55  analyst=Grizzlies
[DRY-RUN] BUY  BEAT   notional=$500  @0.9  analyst=Grizzlies
[DRY-RUN] BUY  CLSK   notional=$500  @0.55  analyst=Grizzlies
[DRY-RUN] SELL CLSK   notional=$500  @0.55  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  CLSK   notional=$500  @0.75  analyst=Grizzlies
[DRY-RUN] SELL CLSK   notional=$500  @0.75  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY_COVER MARA   notional=$250  @1.32  analyst=Grizzlies  pnl=-50.0000 (+20.00%)
[DRY-RUN] BUY_COVER MARA   notional=$250  @1.1  analyst=Grizzlies  pnl=-0.0000 (+0.00%)
[DRY-RUN] BUY  MARA   notional=$500  @0.55  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$250  @0.55  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL_SHORT CLSK   notional=$500  @1.0  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$250  @0.55  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY_COVER CLSK   notional=$500  @1.0  analyst=Grizzlies  pnl=-0.0000 (+0.00%)
[DRY-RUN] BUY  CLSK   notional=$500  @0.8  analyst=Grizzlies
[DRY-RUN] ADD  CLSK   notional=$250  @16.0  analyst=Grizzlies
[WARN] price sanity: BTC exit=62425.634 vs entry=1.1 (56750.6x) -- break-even fallback
  [DRY-RUN] SELL BTC    notional=$500  @1.1  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL HOOD   notional=$500  @0.45  analyst=Grizzlies  pnl=-90.9091 (-18.18%)
[DRY-RUN] BUY  ORDI   notional=$500  @78.4  analyst=Grizzlies
[DRY-RUN] BUY  NVDA   notional=$500  @3.6  analyst=Grizzlies
[DRY-RUN] BUY  AVAX   notional=$500  @52.5  analyst=Grizzlies
[DRY-RUN] BUY  INJ    notional=$500  @50.3  analyst=Grizzlies
[DRY-RUN] BUY  BNB    notional=$500  @593.0  analyst=Grizzlies
[DRY-RUN] BUY  BTC    notional=$500  @73100.0  analyst=Grizzlies
[DRY-RUN] BUY  SOL    notional=$500  @170.5  analyst=Grizzlies
[DRY-RUN] SELL BTC    notional=$250  @63455.6845  analyst=Grizzlies  pnl=-32.9833 (-13.19%)
[DRY-RUN] SELL BTC    notional=$125  @63542.1015  analyst=Grizzlies  pnl=-16.3439 (-13.08%)
[DRY-RUN] ADD  BTC    notional=$250  @65000.0  analyst=Grizzlies
[DRY-RUN] SELL SOL    notional=$250  @170.5  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL BTC    notional=$62  @66360.8325  analyst=Grizzlies  pnl=-5.7619 (-9.22%)
[DRY-RUN] SELL SOL    notional=$250  @170.5  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  ETH    notional=$500  @3110.0  analyst=Grizzlies
[DRY-RUN] SELL ETH    notional=$250  @3044.14  analyst=Grizzlies  pnl=-5.2942 (-2.12%)
[DRY-RUN] SELL BTC    notional=$31  @61898.9865  analyst=Grizzlies  pnl=-4.7884 (-15.32%)
[DRY-RUN] SELL ETH    notional=$125  @2971.1255  analyst=Grizzlies  pnl=-5.5818 (-4.47%)
[DRY-RUN] SELL ETH    notional=$62  @3081.65  analyst=Grizzlies  pnl=-0.5697 (-0.91%)
[DRY-RUN] SELL BNB    notional=$250  @593.0  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL ETH    notional=$62  @3533.75  analyst=Grizzlies  pnl=+8.5159 (+13.63%)
[DRY-RUN] SELL CLSK   notional=$250  @0.96  analyst=Grizzlies  pnl=+50.0000 (+20.00%)
[DRY-RUN] SELL CLSK   notional=$125  @1.12  analyst=Grizzlies  pnl=+50.0000 (+40.00%)
[DRY-RUN] BUY  ETH    notional=$500  @3540.0  analyst=Grizzlies
[DRY-RUN] SELL CLSK   notional=$125  @0.8  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  MARA   notional=$500  @0.7  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$250  @0.805  analyst=Grizzlies  pnl=+37.5000 (+15.00%)
[DRY-RUN] SELL MARA   notional=$125  @0.945  analyst=Grizzlies  pnl=+43.7500 (+35.00%)
[DRY-RUN] SELL MARA   notional=$125  @0.7  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  USDT   notional=$500  @2420.0  analyst=Grizzlies
[DRY-RUN] SELL BEAT   notional=$500  @0.45  analyst=Grizzlies  pnl=-250.0000 (-50.00%)
[DRY-RUN] BUY  ENS    notional=$500  @27.2  analyst=Grizzlies
[DRY-RUN] SELL ENS    notional=$500  @27.2  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  MARA   notional=$500  @0.45  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$250  @0.6075  analyst=Grizzlies  pnl=+87.5000 (+35.00%)
[DRY-RUN] SELL MARA   notional=$125  @0.585  analyst=Grizzlies  pnl=+37.5000 (+30.00%)
[DRY-RUN] SELL MARA   notional=$62  @0.5175  analyst=Grizzlies  pnl=+9.3750 (+15.00%)
[DRY-RUN] SELL MARA   notional=$31  @0.6075  analyst=Grizzlies  pnl=+10.9375 (+35.00%)
[DRY-RUN] SELL MARA   notional=$16  @0.504  analyst=Grizzlies  pnl=+1.8750 (+12.00%)
[DRY-RUN] SELL MARA   notional=$8  @0.585  analyst=Grizzlies  pnl=+2.3437 (+30.00%)
[DRY-RUN] SELL MARA   notional=$4  @0.65  analyst=Grizzlies  pnl=+1.7361 (+44.44%)
[DRY-RUN] SELL MARA   notional=$2  @0.54  analyst=Grizzlies  pnl=+0.3906 (+20.00%)
[DRY-RUN] SELL MARA   notional=$1  @0.6075  analyst=Grizzlies  pnl=+0.3418 (+35.00%)
[DRY-RUN] SELL MARA   notional=$1  @0.45  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  MARA   notional=$500  @0.4  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$250  @0.48  analyst=Grizzlies  pnl=+50.0000 (+20.00%)
[DRY-RUN] SELL MARA   notional=$125  @0.56  analyst=Grizzlies  pnl=+50.0000 (+40.00%)
[DRY-RUN] SELL MARA   notional=$62  @0.48  analyst=Grizzlies  pnl=+12.5000 (+20.00%)
[DRY-RUN] SELL MARA   notional=$31  @0.56  analyst=Grizzlies  pnl=+12.5000 (+40.00%)
[DRY-RUN] SELL MARA   notional=$16  @0.64  analyst=Grizzlies  pnl=+9.3750 (+60.00%)
[DRY-RUN] SELL MARA   notional=$16  @0.4  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  ONDO   notional=$500  @0.95  analyst=Grizzlies
[DRY-RUN] SELL BTC    notional=$16  @59353.8  analyst=Grizzlies  pnl=-2.9382 (-18.80%)
[DRY-RUN] SELL BTC    notional=$8  @60721.87  analyst=Grizzlies  pnl=-1.3229 (-16.93%)
[DRY-RUN] SELL BTC    notional=$4  @63426.4645  analyst=Grizzlies  pnl=-0.5169 (-13.23%)
[DRY-RUN] SELL BTC    notional=$2  @62383.6545  analyst=Grizzlies  pnl=-0.2863 (-14.66%)
[DRY-RUN] SELL BTC    notional=$2  @60243.3  analyst=Grizzlies  pnl=-0.3435 (-17.59%)
[DRY-RUN] BUY  BTC    notional=$500  @60200.0  analyst=Grizzlies
[DRY-RUN] SELL BTC    notional=$250  @60264.59  analyst=Grizzlies  pnl=+0.2682 (+0.11%)
[DRY-RUN] SELL BTC    notional=$250  @57751.966  analyst=Grizzlies  pnl=-10.1663 (-4.07%)
[DRY-RUN] BUY  MARA   notional=$500  @0.42  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$500  @0.42  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  MARA   notional=$500  @59750.0  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$250  @72895.0  analyst=Grizzlies  pnl=+55.0000 (+22.00%)
[DRY-RUN] SELL MARA   notional=$125  @89625.0  analyst=Grizzlies  pnl=+62.5000 (+50.00%)
[WARN] price sanity: MARA exit=38.0 vs entry=59750.0 (0.0x) -- break-even fallback
  [DRY-RUN] SELL MARA   notional=$62  @59750.0  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL MARA   notional=$31  @68712.5  analyst=Grizzlies  pnl=+4.6875 (+15.00%)
[DRY-RUN] SELL MARA   notional=$16  @83650.0  analyst=Grizzlies  pnl=+6.2500 (+40.00%)
[DRY-RUN] SELL MARA   notional=$8  @71700.0  analyst=Grizzlies  pnl=+1.5625 (+20.00%)
[DRY-RUN] SELL MARA   notional=$4  @80662.5  analyst=Grizzlies  pnl=+1.3672 (+35.00%)
[DRY-RUN] SELL MARA   notional=$4  @59750.0  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  MARA   notional=$500  @0.45  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$250  @0.5265  analyst=Grizzlies  pnl=+42.5000 (+17.00%)
[DRY-RUN] SELL MARA   notional=$125  @0.45  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL MARA   notional=$62  @0.6075  analyst=Grizzlies  pnl=+21.8750 (+35.00%)
[DRY-RUN] SELL MARA   notional=$31  @0.675  analyst=Grizzlies  pnl=+15.6250 (+50.00%)
[DRY-RUN] SELL MARA   notional=$16  @0.855  analyst=Grizzlies  pnl=+14.0625 (+90.00%)
[DRY-RUN] SELL MARA   notional=$8  @0.9  analyst=Grizzlies  pnl=+7.8125 (+100.00%)
[DRY-RUN] SELL MARA   notional=$4  @0.54  analyst=Grizzlies  pnl=+0.7813 (+20.00%)
[DRY-RUN] SELL MARA   notional=$4  @0.45  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  HOOD   notional=$500  @0.37  analyst=Grizzlies
[DRY-RUN] SELL HOOD   notional=$250  @0.444  analyst=Grizzlies  pnl=+50.0000 (+20.00%)
[DRY-RUN] SELL ETH    notional=$250  @3693.9245  analyst=Grizzlies  pnl=+10.8704 (+4.35%)
[DRY-RUN] SELL ETH    notional=$250  @3639.718560794  analyst=Grizzlies  pnl=+7.0423 (+2.82%)
[DRY-RUN] BUY  LINK   notional=$500  @22.5  analyst=Grizzlies
[DRY-RUN] SELL LINK   notional=$250  @27.0  analyst=Grizzlies  pnl=+50.0000 (+20.00%)
[DRY-RUN] SELL LINK   notional=$250  @22.5  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  MARA   notional=$500  @0.25  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$250  @0.325  analyst=Grizzlies  pnl=+75.0000 (+30.00%)
[DRY-RUN] SELL MARA   notional=$125  @0.25  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL MARA   notional=$62  @0.5  analyst=Grizzlies  pnl=+62.5000 (+100.00%)
[DRY-RUN] SELL MARA   notional=$31  @0.3125  analyst=Grizzlies  pnl=+7.8125 (+25.00%)
[DRY-RUN] SELL MARA   notional=$16  @0.3375  analyst=Grizzlies  pnl=+5.4688 (+35.00%)
[DRY-RUN] SELL MARA   notional=$8  @0.4  analyst=Grizzlies  pnl=+4.6875 (+60.00%)
[DRY-RUN] SELL MARA   notional=$8  @0.25  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  BTC    notional=$500  @96250.0  analyst=Grizzlies
[DRY-RUN] SELL BTC    notional=$250  @97037.834  analyst=Grizzlies  pnl=+2.0463 (+0.82%)
[DRY-RUN] SELL HOOD   notional=$125  @0.74  analyst=Grizzlies  pnl=+125.0000 (+100.00%)
[DRY-RUN] SELL HOOD   notional=$62  @0.888  analyst=Grizzlies  pnl=+87.5000 (+140.00%)
[DRY-RUN] SELL BTC    notional=$125  @96423.0394639998  analyst=Grizzlies  pnl=+0.2247 (+0.18%)
[DRY-RUN] SELL BTC    notional=$62  @81647.943  analyst=Grizzlies  pnl=-9.4819 (-15.17%)
[DRY-RUN] SELL BTC    notional=$62  @84169.75  analyst=Grizzlies  pnl=-7.8443 (-12.55%)
[DRY-RUN] SELL_SHORT MARA   notional=$500  @0.75  analyst=Grizzlies
[DRY-RUN] BUY_COVER MARA   notional=$250  @0.8625  analyst=Grizzlies  pnl=-37.5000 (+15.00%)
[DRY-RUN] BUY_COVER MARA   notional=$125  @1.125  analyst=Grizzlies  pnl=-62.5000 (+50.00%)
[DRY-RUN] BUY_COVER MARA   notional=$62  @1.275  analyst=Grizzlies  pnl=-43.7500 (+70.00%)
[DRY-RUN] SELL HOOD   notional=$62  @0.1924  analyst=Grizzlies  pnl=-30.0000 (-48.00%)
[DRY-RUN] BUY  ENA    notional=$500  @0.34  analyst=Grizzlies
[DRY-RUN] BUY_COVER MARA   notional=$62  @0.3  analyst=Grizzlies  pnl=+37.5000 (-60.00%)
[DRY-RUN] SELL ENA    notional=$250  @0.34  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL ENA    notional=$125  @0.34  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  HOOD   notional=$500  @0.7  analyst=Grizzlies
[DRY-RUN] SELL HOOD   notional=$250  @0.875  analyst=Grizzlies  pnl=+62.5000 (+25.00%)
[DRY-RUN] SELL HOOD   notional=$125  @0.98  analyst=Grizzlies  pnl=+50.0000 (+40.00%)
[DRY-RUN] SELL HOOD   notional=$62  @1.19  analyst=Grizzlies  pnl=+43.7500 (+70.00%)
[DRY-RUN] SELL HOOD   notional=$31  @0.805  analyst=Grizzlies  pnl=+4.6875 (+15.00%)
[DRY-RUN] SELL HOOD   notional=$16  @0.945  analyst=Grizzlies  pnl=+5.4688 (+35.00%)
[DRY-RUN] SELL HOOD   notional=$8  @1.05  analyst=Grizzlies  pnl=+3.9063 (+50.00%)
[DRY-RUN] SELL HOOD   notional=$4  @0.98  analyst=Grizzlies  pnl=+1.5625 (+40.00%)
[DRY-RUN] SELL HOOD   notional=$2  @1.19  analyst=Grizzlies  pnl=+1.3672 (+70.00%)
[DRY-RUN] SELL HOOD   notional=$1  @1.4  analyst=Grizzlies  pnl=+0.9766 (+100.00%)
[DRY-RUN] SELL HOOD   notional=$1  @0.546  analyst=Grizzlies  pnl=-0.2148 (-22.00%)
[DRY-RUN] BUY  MARA   notional=$500  @0.5  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$500  @0.5  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  MARA   notional=$500  @0.3  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$250  @0.333  analyst=Grizzlies  pnl=+27.5000 (+11.00%)
[DRY-RUN] SELL MARA   notional=$250  @0.234  analyst=Grizzlies  pnl=-55.0000 (-22.00%)
[DRY-RUN] BUY  ETH    notional=$500  @2662.0  analyst=Grizzlies
[DRY-RUN] SELL ENA    notional=$62  @0.34  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL ETH    notional=$250  @2513.6671354675  analyst=Grizzlies  pnl=-13.9306 (-5.57%)
[DRY-RUN] SELL ENA    notional=$31  @0.34  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL ENA    notional=$16  @0.34  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL ENA    notional=$16  @0.34  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL_SHORT MARA   notional=$500  @0.28  analyst=Grizzlies
[DRY-RUN] BUY_COVER MARA   notional=$250  @0.322  analyst=Grizzlies  pnl=-37.5000 (+15.00%)
[DRY-RUN] BUY_COVER MARA   notional=$250  @0.28  analyst=Grizzlies  pnl=-0.0000 (+0.00%)
[DRY-RUN] BUY  BTC    notional=$500  @108400.0  analyst=Grizzlies
[DRY-RUN] SELL ETH    notional=$250  @2659.0735  analyst=Grizzlies  pnl=-0.2748 (-0.11%)
[DRY-RUN] SELL_SHORT MARA   notional=$500  @0.36  analyst=Grizzlies
[DRY-RUN] BUY_COVER MARA   notional=$500  @0.144  analyst=Grizzlies  pnl=+300.0000 (-60.00%)
[DRY-RUN] BUY  MARA   notional=$500  @0.75  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$250  @0.9  analyst=Grizzlies  pnl=+50.0000 (+20.00%)
[DRY-RUN] SELL MARA   notional=$250  @0.75  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  MARA   notional=$500  @0.82  analyst=Grizzlies
[DRY-RUN] SELL MARA   notional=$500  @0.82  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  HOOD   notional=$500  @0.99  analyst=Grizzlies
[DRY-RUN] SELL HOOD   notional=$500  @0.99  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL_SHORT MARA   notional=$500  @0.55  analyst=Grizzlies
[DRY-RUN] BUY_COVER MARA   notional=$250  @0.6325  analyst=Grizzlies  pnl=-37.5000 (+15.00%)
[DRY-RUN] BUY_COVER MARA   notional=$125  @0.6875  analyst=Grizzlies  pnl=-31.2500 (+25.00%)
[DRY-RUN] BUY_COVER MARA   notional=$62  @0.6215  analyst=Grizzlies  pnl=-8.1250 (+13.00%)
[DRY-RUN] BUY_COVER MARA   notional=$31  @0.6875  analyst=Grizzlies  pnl=-7.8125 (+25.00%)
[DRY-RUN] BUY_COVER MARA   notional=$31  @0.374  analyst=Grizzlies  pnl=+10.0000 (-32.00%)
[DRY-RUN] BUY  ETH    notional=$500  @3720.0  analyst=Grizzlies
[DRY-RUN] SELL ETH    notional=$250  @3816.365  analyst=Grizzlies  pnl=+6.4761 (+2.59%)
[DRY-RUN] SELL ETH    notional=$125  @3842.08  analyst=Grizzlies  pnl=+4.1022 (+3.28%)
[DRY-RUN] SELL BNB    notional=$125  @593.0  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL ETH    notional=$62  @3654.2625  analyst=Grizzlies  pnl=-1.1045 (-1.77%)
[DRY-RUN] SELL ETH    notional=$31  @3691.165  analyst=Grizzlies  pnl=-0.2422 (-0.78%)
[DRY-RUN] SELL ETH    notional=$31  @3747.9875  analyst=Grizzlies  pnl=+0.2351 (+0.75%)
[DRY-RUN] SELL BTC    notional=$500  @115006.924  analyst=Grizzlies  pnl=+30.4747 (+6.09%)
[DRY-RUN] BUY  ETH    notional=$500  @3790.0  analyst=Grizzlies
[DRY-RUN] SELL_SHORT MARA   notional=$500  @0.6  analyst=Grizzlies
[DRY-RUN] BUY_COVER MARA   notional=$250  @0.69  analyst=Grizzlies  pnl=-37.5000 (+15.00%)
[DRY-RUN] BUY_COVER MARA   notional=$125  @0.78  analyst=Grizzlies  pnl=-37.5000 (+30.00%)
[DRY-RUN] BUY_COVER MARA   notional=$62  @0.84  analyst=Grizzlies  pnl=-25.0000 (+40.00%)
[DRY-RUN] SELL ETH    notional=$250  @3786.9205  analyst=Grizzlies  pnl=-0.2031 (-0.08%)
[DRY-RUN] SELL ETH    notional=$250  @3809.99  analyst=Grizzlies  pnl=+1.3186 (+0.53%)
[DRY-RUN] BUY_COVER MARA   notional=$31  @0.6  analyst=Grizzlies  pnl=-0.0000 (+0.00%)
[DRY-RUN] BUY_COVER MARA   notional=$16  @0.6  analyst=Grizzlies  pnl=-0.0000 (+0.00%)
[DRY-RUN] BUY  ETH    notional=$500  @3786.0  analyst=Grizzlies
[DRY-RUN] SELL ETH    notional=$250  @3797.62  analyst=Grizzlies  pnl=+0.7673 (+0.31%)
[DRY-RUN] SELL ETH    notional=$125  @3813.2  analyst=Grizzlies  pnl=+0.8980 (+0.72%)
[DRY-RUN] BUY_COVER MARA   notional=$16  @0.6  analyst=Grizzlies  pnl=-0.0000 (+0.00%)
[DRY-RUN] BUY  SUI    notional=$500  @3.77  analyst=Grizzlies
[DRY-RUN] SELL SUI    notional=$250  @3.77  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL SUI    notional=$125  @3.77  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL SUI    notional=$125  @3.77  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  SOL    notional=$500  @205.1  analyst=Grizzlies
[DRY-RUN] SELL ETH    notional=$62  @4333.045  analyst=Grizzlies  pnl=+9.0307 (+14.45%)
[DRY-RUN] SELL ETH    notional=$31  @4278.7565  analyst=Grizzlies  pnl=+4.0673 (+13.02%)
[DRY-RUN] SELL ETH    notional=$31  @4618.2675  analyst=Grizzlies  pnl=+6.8696 (+21.98%)
[DRY-RUN] BUY  BTC    notional=$500  @114300.0  analyst=Grizzlies
[DRY-RUN] SELL BTC    notional=$250  @109572.69  analyst=Grizzlies  pnl=-10.3397 (-4.14%)
[DRY-RUN] SELL BTC    notional=$125  @110703.185  analyst=Grizzlies  pnl=-3.9335 (-3.15%)
[DRY-RUN] SELL SOL    notional=$250  @237.865  analyst=Grizzlies  pnl=+39.9378 (+15.98%)
[DRY-RUN] SELL SOL    notional=$125  @240.5009  analyst=Grizzlies  pnl=+21.5754 (+17.26%)
[DRY-RUN] SELL BTC    notional=$62  @115883.87  analyst=Grizzlies  pnl=+0.8661 (+1.39%)
[DRY-RUN] SELL BTC    notional=$31  @115439.9395  analyst=Grizzlies  pnl=+0.3117 (+1.00%)
[DRY-RUN] SELL BTC    notional=$16  @116144.295  analyst=Grizzlies  pnl=+0.2521 (+1.61%)
[DRY-RUN] SELL BNB    notional=$62  @593.0  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL BNB    notional=$31  @593.0  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL BTC    notional=$16  @108549.105  analyst=Grizzlies  pnl=-0.7862 (-5.03%)
[DRY-RUN] BUY  BTC    notional=$500  @109400.0  analyst=Grizzlies
[DRY-RUN] SELL BTC    notional=$250  @110852.95  analyst=Grizzlies  pnl=+3.3203 (+1.33%)
[DRY-RUN] SELL BTC    notional=$125  @111671.045  analyst=Grizzlies  pnl=+2.5949 (+2.08%)
[DRY-RUN] SELL BTC    notional=$125  @112031.814  analyst=Grizzlies  pnl=+3.0071 (+2.41%)
[DRY-RUN] BUY  TAO    notional=$500  @428.0  analyst=Grizzlies
[DRY-RUN] SELL TAO    notional=$500  @428.0  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  TAO    notional=$500  @353.2  analyst=Grizzlies
[DRY-RUN] SELL TAO    notional=$500  @353.2  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  TAO    notional=$500  @339.5  analyst=Grizzlies
[DRY-RUN] SELL TAO    notional=$250  @339.5  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL TAO    notional=$125  @339.5  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL TAO    notional=$125  @339.5  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  ETH    notional=$500  @2030.0  analyst=Grizzlies
[DRY-RUN] SELL ETH    notional=$500  @2059.78  analyst=Grizzlies  pnl=+7.3350 (+1.47%)
[DRY-RUN] BUY  ETH    notional=$500  @2030.0  analyst=Grizzlies
[DRY-RUN] SELL ETH    notional=$500  @2059.78  analyst=Grizzlies  pnl=+7.3350 (+1.47%)
[DRY-RUN] SELL_SHORT BTC    notional=$500  @69150.0  analyst=Grizzlies
[DRY-RUN] BUY_COVER BTC    notional=$500  @71520.85  analyst=Grizzlies  pnl=-17.1428 (+3.43%)
[DRY-RUN] SELL_SHORT BTC    notional=$500  @71200.0  analyst=Grizzlies
[DRY-RUN] BUY_COVER BTC    notional=$500  @72105.565  analyst=Grizzlies  pnl=-6.3593 (+1.27%)
[DRY-RUN] SELL_SHORT BTC    notional=$500  @72200.0  analyst=Grizzlies
[DRY-RUN] BUY_COVER BTC    notional=$500  @69370.0  analyst=Grizzlies  pnl=+19.5983 (-3.92%)
[DRY-RUN] BUY  IBIT   notional=$500  @0.82  analyst=Grizzlies
[DRY-RUN] SELL IBIT   notional=$250  @0.9102  analyst=Grizzlies  pnl=+27.5000 (+11.00%)
[DRY-RUN] SELL IBIT   notional=$250  @0.656  analyst=Grizzlies  pnl=-50.0000 (-20.00%)
[DRY-RUN] SELL_SHORT BMNR   notional=$500  @0.7  analyst=Grizzlies
[DRY-RUN] BUY_COVER BMNR   notional=$250  @0.805  analyst=Grizzlies  pnl=-37.5000 (+15.00%)
[DRY-RUN] BUY_COVER BMNR   notional=$125  @0.875  analyst=Grizzlies  pnl=-31.2500 (+25.00%)
[DRY-RUN] BUY_COVER BMNR   notional=$62  @0.798  analyst=Grizzlies  pnl=-8.7500 (+14.00%)
[DRY-RUN] BUY_COVER BMNR   notional=$31  @0.875  analyst=Grizzlies  pnl=-7.8125 (+25.00%)
[DRY-RUN] BUY_COVER BMNR   notional=$31  @0.7  analyst=Grizzlies  pnl=-0.0000 (+0.00%)
[DRY-RUN] BUY  IBIT   notional=$500  @0.44  analyst=Grizzlies
[DRY-RUN] SELL IBIT   notional=$250  @0.572  analyst=Grizzlies  pnl=+75.0000 (+30.00%)
[DRY-RUN] SELL IBIT   notional=$125  @0.638  analyst=Grizzlies  pnl=+56.2500 (+45.00%)
[DRY-RUN] SELL IBIT   notional=$62  @0.682  analyst=Grizzlies  pnl=+34.3750 (+55.00%)
[DRY-RUN] SELL IBIT   notional=$62  @0.44  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  IBIT   notional=$500  @0.25  analyst=Grizzlies
[DRY-RUN] SELL IBIT   notional=$250  @0.3  analyst=Grizzlies  pnl=+50.0000 (+20.00%)
[DRY-RUN] SELL IBIT   notional=$125  @0.2875  analyst=Grizzlies  pnl=+18.7500 (+15.00%)
[DRY-RUN] SELL IBIT   notional=$62  @0.2875  analyst=Grizzlies  pnl=+9.3750 (+15.00%)
[DRY-RUN] SELL IBIT   notional=$31  @0.275  analyst=Grizzlies  pnl=+3.1250 (+10.00%)
[DRY-RUN] SELL IBIT   notional=$16  @0.3  analyst=Grizzlies  pnl=+3.1250 (+20.00%)
[DRY-RUN] SELL IBIT   notional=$16  @0.25  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL_SHORT BTC    notional=$500  @78800.0  analyst=Grizzlies
[DRY-RUN] BUY_COVER BTC    notional=$500  @77990.2745  analyst=Grizzlies  pnl=+5.1379 (-1.03%)
[DRY-RUN] BUY  IBIT   notional=$500  @0.5  analyst=Grizzlies
[DRY-RUN] SELL IBIT   notional=$250  @0.575  analyst=Grizzlies  pnl=+37.5000 (+15.00%)
[DRY-RUN] SELL IBIT   notional=$125  @0.625  analyst=Grizzlies  pnl=+31.2500 (+25.00%)
[DRY-RUN] SELL IBIT   notional=$62  @0.675  analyst=Grizzlies  pnl=+21.8750 (+35.00%)
[DRY-RUN] SELL IBIT   notional=$62  @0.5  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  BTC    notional=$500  @77850.0  analyst=Grizzlies
[DRY-RUN] ADD  SOL    notional=$250  @87.0  analyst=Grizzlies
[DRY-RUN] SELL SOL    notional=$125  @85.27185  analyst=Grizzlies  pnl=-73.0303 (-58.42%)
[DRY-RUN] ADD  BTC    notional=$250  @77800.0  analyst=Grizzlies
[DRY-RUN] BUY  IBIT   notional=$500  @0.68  analyst=Grizzlies
[DRY-RUN] SELL IBIT   notional=$250  @0.782  analyst=Grizzlies  pnl=+37.5000 (+15.00%)
[DRY-RUN] SELL IBIT   notional=$250  @0.68  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] BUY  IBIT   notional=$500  @0.68  analyst=Grizzlies
[DRY-RUN] SELL BTC    notional=$500  @76664.1845  analyst=Grizzlies  pnl=-7.6160 (-1.52%)
[DRY-RUN] BUY  BTC    notional=$500  @76030.0  analyst=Grizzlies
[DRY-RUN] SELL IBIT   notional=$500  @0.68  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL BTC    notional=$250  @75985.2975  analyst=Grizzlies  pnl=-0.1470 (-0.06%)
[DRY-RUN] SELL BTC    notional=$250  @76278.8235  analyst=Grizzlies  pnl=+0.8182 (+0.33%)
[DRY-RUN] BUY  HYPE   notional=$500  @39.2  analyst=Grizzlies
[DRY-RUN] BUY  DOGE   notional=$500  @0.1098  analyst=Grizzlies
[DRY-RUN] SELL DOGE   notional=$250  @0.1098  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
[DRY-RUN] SELL DOGE   notional=$125  @0.1098  analyst=Grizzlies  pnl=+0.0000 (+0.00%)
  [DRY-RUN] [corpus-end] SELL TSLA   notional=$500  @0.55  pnl=$0.00 (no exit in corpus)
  [DRY-RUN] [corpus-end] SELL ORDI   notional=$500  @78.4  pnl=$0.00 (no exit in corpus)
  [DRY-RUN] [corpus-end] SELL NVDA   notional=$500  @3.6  pnl=$0.00 (no exit in corpus)
  [DRY-RUN] [corpus-end] SELL AVAX   notional=$500  @52.5  pnl=$0.00 (no exit in corpus)
  [DRY-RUN] [corpus-end] SELL INJ    notional=$500  @50.3  pnl=$0.00 (no exit in corpus)
  [DRY-RUN] [corpus-end] SELL BNB    notional=$31  @593.0  pnl=$0.00 (no exit in corpus)
  [DRY-RUN] [corpus-end] SELL USDT   notional=$500  @2420.0  pnl=$0.00 (no exit in corpus)
  [DRY-RUN] [corpus-end] SELL ONDO   notional=$500  @0.95  pnl=$0.00 (no exit in corpus)
  [DRY-RUN] [corpus-end] SELL HYPE   notional=$500  @39.2  pnl=$0.00 (no exit in corpus)
  [DRY-RUN] [corpus-end] SELL DOGE   notional=$125  @0.1098  pnl=$0.00 (no exit in corpus)

Report: C:\Users\jakers\Desktop\ProjectDolph2.0\data\Grizzlies\signals\20260617T192343.html