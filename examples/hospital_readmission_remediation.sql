SELECT
    src.discharge_id,
    count(evt.booked_at) AS followup_appointments_booked
FROM discharges_at_decision_time AS src
LEFT JOIN followup_appointments_after_discharge AS evt
    ON evt.patient_id = src.patient_id
   AND evt.available_at <= src.prediction_time
GROUP BY src.discharge_id, src.prediction_time;
