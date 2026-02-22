import snowflake.connector

import config

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def _connect():
    return snowflake.connector.connect(
        account=config.SNOWFLAKE_ACCOUNT,
        user=config.SNOWFLAKE_USER,
        password=config.SNOWFLAKE_PASSWORD,
        warehouse=config.SNOWFLAKE_WAREHOUSE,
        database=config.SNOWFLAKE_DATABASE,
    )


def _query(sql: str, params: dict | None = None) -> list[dict]:
    """Execute *sql* and return rows as a list of dicts."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or {})
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public helpers — each accepts an email domain (e.g. "acme.com")
# ---------------------------------------------------------------------------

def resolve_account_id(email_domain: str) -> str | None:
    """Map an email domain to a Salesforce ACCOUNT_ID via the Contact table."""
    rows = _query(
        """
        SELECT DISTINCT c.ACCOUNT_ID
        FROM PROD_DB.RAW_SALESFORCE_FIVETRAN.CONTACT c
        WHERE LOWER(c.EMAIL) LIKE %(pattern)s
          AND c.ACCOUNT_ID IS NOT NULL
        LIMIT 1
        """,
        {"pattern": f"%@{email_domain.lower()}"},
    )
    return rows[0]["ACCOUNT_ID"] if rows else None


def get_account_overview(account_id: str) -> dict | None:
    rows = _query(
        """
        SELECT ACCOUNT_ID, ACCOUNT_NAME, ACCOUNT_STATUS, CHURN_SCORE, SEGMENT
        FROM PROD_DB.DBT_MART.MART_DIM_ACCOUNTS
        WHERE ACCOUNT_ID = %(aid)s
        LIMIT 1
        """,
        {"aid": account_id},
    )
    return rows[0] if rows else None


def get_active_subscriptions(account_id: str) -> list[dict]:
    return _query(
        """
        SELECT PRODUCT_NAME, ARR_DOLLARS, STATUS
        FROM PROD_DB.DBT_MART.MART_DIM_ZUORA_SUBSCRIPTIONS
        WHERE ACCOUNT_ID = %(aid)s
          AND STATUS = 'Active'
        ORDER BY ARR_DOLLARS DESC
        """,
        {"aid": account_id},
    )


def get_open_opportunities(account_id: str) -> list[dict]:
    return _query(
        """
        SELECT NAME, STAGE_NAME, AMOUNT, NEXT_STEP, CLOSE_DATE
        FROM PROD_DB.RAW_SALESFORCE_FIVETRAN.OPPORTUNITY
        WHERE ACCOUNT_ID = %(aid)s
          AND IS_CLOSED = FALSE
        ORDER BY CLOSE_DATE ASC
        """,
        {"aid": account_id},
    )


def get_upsell_signals(account_id: str) -> list[dict]:
    return _query(
        """
        SELECT CORPORATION_ID, PRODUCT_NAME, MOST_RECENT_SCHEDULE_CALL_DATE
        FROM PROD_DB.DBT_CORE.UPSELL_CLICKS
        WHERE CORPORATION_ID = %(aid)s
        ORDER BY MOST_RECENT_SCHEDULE_CALL_DATE DESC
        LIMIT 20
        """,
        {"aid": account_id},
    )


def get_greenspace(account_id: str) -> list[dict]:
    """Products in the active catalog that the account does NOT currently subscribe to."""
    return _query(
        """
        SELECT p.NAME AS PRODUCT_NAME, p.FAMILY, p.PRODUCT_LINE_C
        FROM PROD_DB.RAW_SALESFORCE_FIVETRAN.PRODUCT_2 p
        WHERE p.IS_ACTIVE = TRUE
          AND p.NAME NOT IN (
              SELECT s.PRODUCT_NAME
              FROM PROD_DB.DBT_MART.MART_DIM_ZUORA_SUBSCRIPTIONS s
              WHERE s.ACCOUNT_ID = %(aid)s
                AND s.STATUS = 'Active'
          )
        ORDER BY p.FAMILY, p.NAME
        """,
        {"aid": account_id},
    )


def get_product_usage(account_id: str) -> list[dict]:
    return _query(
        """
        SELECT USAGE_CATEGORY, COUNT_EVENTS
        FROM PROD_DB.DBT_MART.MART_DIM_PE_PRODUCT_USAGE_FRONTEND_EVENTS
        WHERE ACCOUNT_ID = %(aid)s
        ORDER BY COUNT_EVENTS DESC
        LIMIT 20
        """,
        {"aid": account_id},
    )


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def get_all_account_data(email_domain: str) -> dict:
    """Fetch all Snowflake data for a client identified by email domain.

    Returns a dict with keys: account_id, overview, subscriptions,
    opportunities, upsell_signals, greenspace, product_usage.
    Values are None / empty lists when data is unavailable.
    """
    account_id = resolve_account_id(email_domain)
    if not account_id:
        return {
            "account_id": None,
            "overview": None,
            "subscriptions": [],
            "opportunities": [],
            "upsell_signals": [],
            "greenspace": [],
            "product_usage": [],
        }

    return {
        "account_id": account_id,
        "overview": get_account_overview(account_id),
        "subscriptions": get_active_subscriptions(account_id),
        "opportunities": get_open_opportunities(account_id),
        "upsell_signals": get_upsell_signals(account_id),
        "greenspace": get_greenspace(account_id),
        "product_usage": get_product_usage(account_id),
    }
