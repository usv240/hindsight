SELECT
    application.application_id,
    date_diff(
        'day',
        max(payment.payment_recorded_at),
        application.prediction_time
    ) AS days_since_last_payment
FROM applications_at_decision_time AS application
LEFT JOIN payment_events_after_decision AS payment
    ON payment.customer_id = application.customer_id
   AND payment.available_at <= application.prediction_time
GROUP BY application.application_id, application.prediction_time;
