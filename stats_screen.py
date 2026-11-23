"""
The Stats screen (main menu → Stats): the signed-in profile's study statistics
for the deck chosen on the main menu.

    [← Main menu]  Stats                                   Deck: <name>
    ┌ Studied today ┐ ┌ Days studied ┐ ┌ Streak ┐ ┌ Average ┐
    ┌ Cards studied per day - last 30 days (bars) ─────────────┐
    ┌ Days studied - last 26 weeks (calendar) ─────────────────┐

Drawn on the background picture (backdrop.py); the panels are see-through like
the main menu's New / Due / Total box. Hover a bar or a day for its numbers.
"""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import ttk

import backdrop
import srs
import theme
from backdrop import Backdrop
from cards import ALL
from stats import Stats

BAND = 0.45
PANEL_SHADE = 0.67                     # like the main menu's stats box
# colours of the blue design; drawn in the current theme (theme.tint)
BAR, BAR_TODAY, BAR_EMPTY = "#3d7bea", "#6aa6ff", "#3a3d43"
LEVELS = ("#2b2e33", "#1f3f75", "#2a5bb0", "#3d7bea", "#6aa6ff")   # calendar: none → most
FONT = "Segoe UI"
WEEKS = 26
DAYS = 30


class StatsScreen(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.stats: Stats | None = None
        self.canvas = c = Backdrop(self, band=BAND, layout=self._layout)
        c.pack(fill="both", expand=True)
        c.create_window(0, 0, anchor="w", tags="menu_btn", window=ttk.Button(
            c, text="←  Main menu", command=app.show_home, takefocus=False))
        c.create_text(0, 0, text="Stats", anchor="w", fill="#ffffff", font=(FONT, 15, "bold"), tags="title")
        c.create_text(0, 0, anchor="e", fill=theme.FG, font=(FONT, 11), tags="deck")

    # ------------------------------------------------------------ data
    def refresh(self):
        """Re-read the study log (when the screen is shown)."""
        cards = self.app.cards
        deck_id = cards.selected_deck if cards.deck(cards.selected_deck) else ALL
        self.deck_name = cards.deck_name(deck_id)
        self.stats = Stats(cards.study_log(deck_id), srs.today())
        self.canvas.itemconfigure("deck", text=f"Deck:  {self.deck_name}")
        self.canvas.refresh()

    # ------------------------------------------------------------ drawing
    def _layout(self, w: int, h: int, dots_h: int, header_h: int) -> list[dict]:
        c = self.canvas
        y = max(dots_h / 2, 22)
        c.coords("menu_btn", 14, y)
        x = c.bbox("menu_btn")[2] + 16 if c.bbox("menu_btn") else 140
        c.coords("title", x, y)
        c.coords("deck", w - 20, y)
        c.delete("content")
        st = self.stats
        if st is None:
            return []
        k = max(min(h / 1000, 1.25), 0.62)            # size of everything
        margin = 24
        cw = min(w - 2 * margin, 1100)
        x0 = (w - cw) / 2
        top = header_h + 14 * k
        gap = 16 * k
        panels = []

        # ---- tiles
        tiles = (
            ("Studied today", f"{st.today_cards}", f"card{'s' if st.today_cards != 1 else ''}  ·  "
                                                   f"{st.today_answers} answer{'s' if st.today_answers != 1 else ''}"),
            ("Days studied", f"{st.days_studied}",
             f"since {st.days[0]:%d %b %Y}" if st.days else "none yet"),
            ("Current streak", f"{st.streak}", f"day{'s' if st.streak != 1 else ''} in a row  ·  best {st.longest_streak}"),
            ("Average", f"{st.average:.0f}" if st.average >= 10 else f"{st.average:.1f}",
             "cards per study day"),
        )
        th = 118 * k
        tw = (cw - gap * (len(tiles) - 1)) / len(tiles)
        for i, (label, big, small) in enumerate(tiles):
            tx = x0 + i * (tw + gap)
            panels.append(self._panel((tx, top, tx + tw, top + th), k))
            c.create_text(tx + 16 * k, top + 14 * k, text=label, anchor="nw", fill=theme.MUTED,
                          font=(FONT, -round(14 * k)), tags="content")
            c.create_text(tx + 16 * k, top + 36 * k, text=big, anchor="nw", fill="#ffffff",
                          font=(FONT, -round(40 * k), "bold"), tags="content")
            c.create_text(tx + 16 * k, top + th - 12 * k, text=small, anchor="sw", fill=theme.FG,
                          font=(FONT, -round(12 * k)), width=tw - 24 * k, tags="content")

        # ---- the rest of the height: bars, then the calendar
        rest_top = top + th + gap
        rest = h - margin - rest_top
        cal_h = min(max(rest * 0.45, 150 * k), 260 * k)
        bar_h = rest - cal_h - gap
        self._bars((x0, rest_top, x0 + cw, rest_top + bar_h), k, panels)
        self._calendar((x0, rest_top + bar_h + gap, x0 + cw, rest_top + bar_h + gap + cal_h), k, panels)
        c.tag_raise("tip")
        return panels

    def _panel(self, box, k) -> dict:
        return {"box": box, "radius": 14 * k, "shade": PANEL_SHADE}

    def _heading(self, x, y, text, k):
        self.canvas.create_text(x, y, text=text, anchor="nw", fill="#ffffff",
                                font=(FONT, -round(15 * k), "bold"), tags="content")

    def _bars(self, box, k, panels):
        """Cards studied per day, last DAYS days."""
        c, st = self.canvas, self.stats
        x0, y0, x1, y1 = box
        if y1 - y0 < 80:
            return
        panels.append(self._panel(box, k))
        pad = 18 * k
        self._heading(x0 + pad, y0 + 12 * k, f"Cards studied per day  ·  last {DAYS} days", k)
        days = st.last_days(DAYS)
        most = max((n for _d, n in days), default=0)
        left, right = x0 + pad + 34 * k, x1 - pad
        top, bottom = y0 + 48 * k, y1 - 34 * k
        if top >= bottom:
            return
        if most == 0:
            c.create_text((left + right) / 2, (top + bottom) / 2, fill=theme.MUTED, font=(FONT, -round(13 * k)),
                          text="Nothing studied in the last 30 days yet. Cards you answer in Study show up here.",
                          tags="content")
            return
        # scale: a round number at the top, a faint line at the middle
        step = max(1, round(most / 2 + 0.49))
        scale_top = step * 2
        for v in (0, step, scale_top):
            yy = bottom - (bottom - top) * v / scale_top
            c.create_line(left, yy, right, yy, fill=theme.tint("#3a3d43"), tags="content")
            c.create_text(left - 8 * k, yy, text=str(v), anchor="e", fill=theme.MUTED,
                          font=(FONT, -round(11 * k)), tags="content")
        slot = (right - left) / len(days)
        bw = max(slot * 0.68, 2)
        for i, (d, n) in enumerate(days):
            bx = left + slot * i + (slot - bw) / 2
            by = bottom - (bottom - top) * n / scale_top
            colour = theme.tint(BAR_TODAY if d == st.today else (BAR if n else BAR_EMPTY))
            tag = f"bar{i}"
            c.create_rectangle(bx, min(by, bottom - 2), bx + bw, bottom, fill=colour, outline="",
                               tags=("content", tag))
            # hover anywhere in the day's column
            c.create_rectangle(left + slot * i, top, left + slot * (i + 1), bottom, fill="", outline="",
                               tags=("content", tag))
            self._tip(tag, d, n)
            if i % 5 == (len(days) - 1) % 5:
                c.create_text(bx + bw / 2, bottom + 8 * k, text=f"{d:%b} {d.day}" if d != st.today else "Today",
                              anchor="n", fill=theme.MUTED if d != st.today else theme.FG,
                              font=(FONT, -round(11 * k)), tags="content")

    def _calendar(self, box, k, panels):
        """Days studied, last WEEKS weeks: one square a day, darker = fewer cards."""
        c, st = self.canvas, self.stats
        x0, y0, x1, y1 = box
        if y1 - y0 < 90:
            return
        panels.append(self._panel(box, k))
        pad = 18 * k
        self._heading(x0 + pad, y0 + 12 * k, f"Days studied  ·  last {WEEKS} weeks", k)
        label_w = 34 * k
        top = y0 + 64 * k
        avail_h = y1 - 14 * k - top
        avail_w = x1 - pad - (x0 + pad + label_w)
        cell = max(min(avail_h / 7, avail_w / WEEKS), 6)
        sq = cell * 0.8
        left = x0 + pad + label_w + (avail_w - cell * WEEKS) / 2
        # the grid ends with this week (Monday-first rows)
        end = st.today
        start = end - dt.timedelta(days=end.weekday() + 7 * (WEEKS - 1))
        counts = [n for d, n in st.cards_per_day.items() if start <= d <= end and n]
        ranks = sorted(counts)

        def level(n):
            if not n:
                return 0
            if len(ranks) < 4:
                return 3
            q = sum(1 for r in ranks if r <= n) / len(ranks)
            return 1 if q <= 0.25 else 2 if q <= 0.5 else 3 if q <= 0.8 else 4

        for row, name in ((0, "Mon"), (2, "Wed"), (4, "Fri")):
            c.create_text(left - 8 * k, top + row * cell + sq / 2, text=name, anchor="e", fill=theme.MUTED,
                          font=(FONT, -round(10 * k)), tags="content")
        last_month, label_end = None, -1e9
        for week in range(WEEKS):
            monday = start + dt.timedelta(days=7 * week)
            if monday.month != last_month:
                last_month = monday.month
                lx = left + week * cell
                if lx > label_end + 6 * k:            # skip a label that would overlap the one before
                    t = c.create_text(lx, top - 8 * k, text=f"{monday:%b}", anchor="sw",
                                      fill=theme.MUTED, font=(FONT, -round(10 * k)), tags="content")
                    label_end = c.bbox(t)[2]
            for row in range(7):
                d = monday + dt.timedelta(days=row)
                if d > end:
                    continue
                n = st.cards_per_day.get(d, 0)
                cx, cy = left + week * cell, top + row * cell
                tag = f"cal{week}_{row}"
                c.create_rectangle(cx, cy, cx + sq, cy + sq, fill=theme.tint(LEVELS[level(n)]),
                                   outline=theme.FG if d == st.today else "", tags=("content", tag))
                self._tip(tag, d, n)
        # key
        kx, ky = x1 - pad, y0 + 14 * k
        c.create_text(kx, ky + 6 * k, text="more", anchor="e", fill=theme.MUTED, font=(FONT, -round(10 * k)),
                      tags=("content", "key"))
        kx = c.bbox("key")[0] - 6 * k
        for colour in reversed(LEVELS):
            c.create_rectangle(kx - 12 * k, ky, kx, ky + 12 * k, fill=theme.tint(colour), outline="",
                               tags="content")
            kx -= 15 * k
        c.create_text(kx - 2 * k, ky + 6 * k, text="less", anchor="e", fill=theme.MUTED,
                      font=(FONT, -round(10 * k)), tags="content")

    # ------------------------------------------------------------ hover
    def _tip(self, tag: str, day: dt.date, n: int):
        answers = self.stats.answers_per_day.get(day, 0)
        when = "Today" if day == self.stats.today else f"{day:%a} {day.day} {day:%b %Y}"
        text = f"{when}:  {n} card{'s' if n != 1 else ''}" if n else f"{when}:  not studied"
        if n and answers:
            text += f"  ({answers} answer{'s' if answers != 1 else ''})"
        self.canvas.tag_bind(tag, "<Enter>", lambda e, t=text: self._show_tip(e, t))
        self.canvas.tag_bind(tag, "<Leave>", lambda e: self.canvas.delete("tip"))

    def _show_tip(self, event, text: str):
        c = self.canvas
        c.delete("tip")
        x, y = event.x + 14, event.y - 30
        t = c.create_text(x, y, text=text, anchor="nw", fill="#ffffff", font=(FONT, 10), tags="tip")
        bx0, by0, bx1, by1 = c.bbox(t)
        if bx1 + 8 > c.winfo_width():                 # keep it inside the window
            c.move(t, c.winfo_width() - bx1 - 12, 0)
            bx0, by0, bx1, by1 = c.bbox(t)
        r = c.create_rectangle(bx0 - 8, by0 - 5, bx1 + 8, by1 + 5, fill="#101113", outline="#4a4e56", tags="tip")
        c.tag_raise(t, r)
