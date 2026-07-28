SELECT
    src.transaction_id,
    count(evt.disputed_at) AS disputes_on_account
FROM transactions_at_decision_time AS src
LEFT JOIN disputes_after_authorisation AS evt
    ON evt.account_id = src.account_id
   AND evt.available_at <= src.prediction_time
GROUP BY src.transaction_id, src.prediction_time;
