# Guardian Watchdog Protocol

**Purpose:** Continuously monitor for opportunities and threats across all domains that matter to the principal (you).

---

## Watch Categories

### 1. FINANCIAL

| Watch For | Data Sources | Alert When |
|---|---|---|
| Invoice status | Email, accounting app | Overdue > 7 days |
| Unusual spending | Bank feed, credit cards | Spend > 2x average for category |
| Investment moves | Portfolio tracker | Position moves > 5% in a day |
| Business opportunities | Industry newsletters, listings | Match score > 80% |
| Market conditions | News feeds, market data | Major event in your sectors |
| Contract renewals | Calendar, email | < 30 days to expiration |
| Pricing changes | Subscriptions, vendors | Price increase announced |

**Alert format:**
```
💰 FINANCIAL ALERT

What: [Description]
Impact: $[Amount] or [Percentage] affected
Urgency: [NOW / THIS WEEK / MONITOR]
Action: [Specific recommendation]
```

### 2. HEALTH

| Watch For | Data Sources | Alert When |
|---|---|---|
| Sleep patterns | Sleep tracker, evening logs | < 6 hours for 3+ nights |
| Exercise gaps | Daily logs, calendar | 0 exercise for 4+ days |
| Energy trends | Evening log (1-10 rating) | 3+ day declining trend |
| Stress indicators | Calendar density, response times | Overload signals |
| Appointment due | Medical records, calendar | Checkup overdue |
| Habit streaks | Habit tracker | Streak at risk of breaking |

**Alert format:**
```
🏥 HEALTH ALERT

Pattern: [What was noticed]
Trend: [Data over time]
Risk: [What could happen if ignored]
Suggestion: [Specific action]
```

### 3. RELATIONSHIPS

| Watch For | Data Sources | Alert When |
|---|---|---|
| Overdue contacts | Contact CRM, email, calendar | Key person > X days since contact |
| Upcoming occasions | Calendar, contact birthdays | Birthday/anniversary in < 7 days |
| Response gaps | Email, messages | VIP contact waiting > 48 hours |
| Relationship health | Communication frequency | Declining engagement pattern |
| New connection follow-up | Recent meetings, events | Met someone, no follow-up in 7 days |

**Alert format:**
```
👥 RELATIONSHIP ALERT

Who: [Person]
Last contact: [Date/time]
Why it matters: [Their importance to you]
Suggested action: [Specific outreach]
Draft ready: [Yes/No]
```

### 4. OPPORTUNITIES

| Watch For | Data Sources | Alert When |
|---|---|---|
| Job postings | LinkedIn, job boards | Match score > 85% |
| Freelance gigs | Upwork, industry boards | Match + rate > threshold |
| Businesses for sale | BizBuySell, brokers, industry | Industry match + price range |
| Investment opportunities | Angel lists, your network | Matches criteria |
| Partnership potential | Industry news, intros | High synergy signal |
| Speaking/content opportunities | Conferences, podcasts | Topic match |
| Real estate deals | Listings in target areas | Price drop or new listing match |

**Alert format:**
```
🎯 OPPORTUNITY ALERT

Type: [Job / Gig / Business / Investment / Partnership]
What: [Description]
Match score: [X%]
Why it fits: [Specific reasons]
Time sensitivity: [Application deadline / First-mover advantage]
Action: [Specific next step]
Link: [URL if applicable]
```

### 5. THREATS

| Watch For | Data Sources | Alert When |
|---|---|---|
| Security alerts | Email, security services | Any credential/breach mention |
| Contract risks | Contracts, calendar | Unfavorable clause or expiration |
| Deadline risks | Calendar, project trackers | Deadline at risk based on velocity |
| Reputation mentions | Google alerts, social | Your name + negative context |
| Competitor moves | Industry news | Direct competitive action |
| Regulatory changes | Industry newsletters | Rules changing in your space |
| Tech deprecation | Dev news, dependencies | Technology you use being sunset |

**Alert format:**
```
⚠️ THREAT ALERT

Type: [Security / Legal / Deadline / Reputation / Competitive / Regulatory]
What: [Description]
Risk level: [CRITICAL / HIGH / MEDIUM]
Time to act: [Immediate / This week / This month]
Mitigation: [What to do]
```

### 6. MARKET INTEL

| Watch For | Data Sources | Alert When |
|---|---|---|
| Industry news | RSS feeds, newsletters | Major event in your sectors |
| Competitor updates | Company blogs, news | Product launch, funding, pivot |
| Technology shifts | Tech news, Hacker News | Emerging tech relevant to you |
| Economic indicators | Financial news | Recession signals, rate changes |
| Regulatory movements | Government feeds | New rules affecting your work |
| Trend emergence | Social media, search trends | Rising trend in your domain |

**Alert format:**
```
📊 MARKET INTEL

What: [Event or trend]
Source: [Where this came from]
Relevance: [Why it matters to you]
Implication: [What this means for your decisions]
Action: [Adjust strategy? Monitor? Act now?]
```

---

## Alert Priority Matrix

| Priority | Response Time | Example |
|---|---|---|
| **P0 — CRITICAL** | Immediate alert | Security breach, major financial loss, legal threat |
| **P1 — URGENT** | Within hours | Overdue invoice, deadline at risk, hot opportunity |
| **P2 — IMPORTANT** | Daily summary | Relationship overdue, health trend, market shift |
| **P3 — INFORMATIONAL** | Weekly digest | Industry news, minor trends, nice-to-know |

---

## Watch Configuration

Set up watches for each category:

```yaml
watches:
  financial:
    invoice_overdue_days: 7
    spending_anomaly_multiplier: 2.0
    investment_alert_threshold_percent: 5
    contract_renewal_warning_days: 30

  health:
    min_sleep_hours: 6
    max_exercise_gap_days: 4
    energy_trend_window_days: 3

  relationships:
    key_contacts:
      - name: "Mom"
        max_gap_days: 7
      - name: "Best Friend"
        max_gap_days: 14
      - name: "Key Client"
        max_gap_days: 21
    vip_response_max_hours: 48

  opportunities:
    job_match_threshold: 85
    freelance_min_rate: 100
    business_max_price: 500000
    business_industries: ["saas", "ecommerce", "consulting"]

  threats:
    security_alert_keywords: ["breach", "password", "compromised"]
    deadline_risk_window_days: 7

  market:
    industries: ["your_industry_1", "your_industry_2"]
    competitors: ["competitor_1", "competitor_2"]
    technologies: ["tech_1", "tech_2"]
```

---

## Watch Scan Schedule

| Scan Type | Frequency | What's Checked |
|---|---|---|
| **Real-time** | Continuous | Security alerts, P0 threats |
| **Hourly** | Every hour | Email, messages, calendar changes |
| **Morning** | 6:00 AM | Overnight news, market pre-open, opportunities |
| **Midday** | 12:00 PM | Email catch-up, deadline check |
| **Evening** | 5:00 PM | End-of-day summary, next-day prep |
| **Weekly** | Sunday | Full audit, relationship check, goal progress |
| **Monthly** | 1st of month | Strategic review, portfolio health, trend analysis |

---

## Guardian Output: Daily Summary

```
🛡️ GUARDIAN DAILY SUMMARY — [Date]

━━━━ CRITICAL (Act Now) ━━━━
[List P0/P1 items or "Nothing critical"]

━━━━ TODAY'S WATCH ━━━━
💰 Financial: [Status summary]
🏥 Health: [Status summary]
👥 Relationships: [Status summary]
🎯 Opportunities: [New items or "None"]
⚠️ Threats: [Active threats or "Clear"]
📊 Market: [Key updates or "Quiet"]

━━━━ ACTION ITEMS ━━━━
1. [Most important action]
2. [Second action]
3. [Third action]

━━━━ WATCHING ━━━━
• [Item 1 being monitored]
• [Item 2 being monitored]
```

---

## Guardian vs. Reactive Mode

| Traditional AI | Guardian Mode |
|---|---|
| Waits for you to ask | Proactively scans |
| Tells you what happened | Tells you what's coming |
| Reports facts | Reports + recommends |
| Generic alerts | Personalized to your priorities |
| One-time responses | Continuous monitoring |

The Guardian never sleeps. It's always watching your interests.
