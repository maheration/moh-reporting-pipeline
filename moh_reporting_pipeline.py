import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def prepare_report(opd_file, liver_file, kidney_recipient_file, kidney_donor_file, historical_visits_file):
    df = pd.read_excel(opd_file)
    cols_to_drop = ['regtime', 'ARRIVETIME', 'STARTTIME', 'PORTAL STATUS', 'clinic_key', 'JOB TITLE', 'SPECIALTY', 'Added_by', 'addtime']
    df = df.drop(columns=cols_to_drop)
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    df['visit_datetime'] = pd.to_datetime(df['visit_datetime'], errors='coerce').dt.date
    df['mrn'] = pd.to_numeric(df['mrn'], errors='coerce')
    new_cols = ['liver_r_d', 'liver_status', 'kidney_recipient', 'kidney_donor']
    for col in new_cols:
        df[col] = None
    df = df[df['visit_status'] != 'NO SHOW']
    liver_df = pd.read_excel(liver_file)
    liver_df.columns = liver_df.columns.str.strip().str.lower().str.replace(' ', '_')
    df = df.merge(liver_df[['r_mrn', 'rec_don', 'current_status1']], left_on='mrn', right_on='r_mrn', how='left')
    df['liver_r_d'] = df['rec_don']
    df['liver_status'] = df['current_status1']
    df = df.drop(columns=['r_mrn', 'rec_don', 'current_status1'])
    kidney_rec_df = pd.read_excel(kidney_recipient_file)
    kidney_rec_df.columns = kidney_rec_df.columns.str.strip().str.lower().str.replace(' ', '_')
    df = df.merge(kidney_rec_df[['r_mrn', 'current_status1']], left_on='mrn', right_on='r_mrn', how='left')
    df['kidney_recipient'] = df['current_status1']
    df = df.drop(columns=['r_mrn', 'current_status1'])
    kidney_donor_df = pd.read_excel(kidney_donor_file)
    kidney_donor_df.columns = kidney_donor_df.columns.str.strip().str.lower().str.replace(' ', '_')
    df = df.merge(kidney_donor_df[['d_mrn', 'current_status1_d']], left_on='mrn', right_on='d_mrn', how='left')
    df['kidney_donor'] = df['current_status1_d']
    df = df.drop(columns=['d_mrn', 'current_status1_d'])
    mask = df['clinic_name'].isin(['Anesthesia', 'Clinical Nutrition']) & df['liver_r_d'].isna() & df['kidney_recipient'].isna() & df['kidney_donor'].isna()
    df = df[~mask]
    df['need_review'] = 'no'
    review_mask = df[['liver_r_d', 'kidney_recipient', 'kidney_donor']].isna().all(axis=1)
    df.loc[review_mask, 'need_review'] = 'yes'
    mask_liver_only = df['liver_r_d'].notna() & df['kidney_recipient'].isna() & df['kidney_donor'].isna()
    mask_k_recip_only = df['kidney_recipient'].notna() & df['liver_r_d'].isna() & df['kidney_donor'].isna()
    mask_k_donor_only = df['kidney_donor'].notna() & df['liver_r_d'].isna() & df['kidney_recipient'].isna()
    df['r_d'] = np.select([mask_liver_only, mask_k_recip_only, mask_k_donor_only], ['Liver ' + df['liver_r_d'].astype(str), df['kidney_recipient'], df['kidney_donor']], default=np.nan)
    mixed_mask = df['liver_r_d'].notna() & (df['kidney_recipient'].notna() | df['kidney_donor'].notna()) & df['r_d'].isna()
    clinic_lower = df['clinic_name'].fillna('').str.lower()
    renal_clinic = clinic_lower.str.contains('renal|kidney')
    liver_clinic = clinic_lower.str.contains('liver')
    df.loc[mixed_mask & renal_clinic & ~liver_clinic, 'r_d'] = df.loc[mixed_mask & renal_clinic & ~liver_clinic, 'kidney_recipient'].fillna(df.loc[mixed_mask & renal_clinic & ~liver_clinic, 'kidney_donor'])
    df.loc[mixed_mask & liver_clinic & ~renal_clinic, 'r_d'] = 'Liver ' + df.loc[mixed_mask & liver_clinic & ~renal_clinic, 'liver_r_d'].astype(str)
    df['patient_type'] = None
    df['transplant_date'] = None
    df['days'] = None
    df['patient_type'] = df['liver_status'].combine_first(df['kidney_recipient']).combine_first(df['kidney_donor'])
    liver_dict = liver_df[['r_mrn', 'surgery_date']].dropna(subset=['r_mrn']).set_index('r_mrn')['surgery_date'].to_dict()
    recip_dict = kidney_rec_df[['r_mrn', 'surgery_date']].dropna(subset=['r_mrn']).set_index('r_mrn')['surgery_date'].to_dict()
    donor_dict = kidney_donor_df[['d_mrn', 'surgery_date_d']].dropna(subset=['d_mrn']).set_index('d_mrn')['surgery_date_d'].to_dict()
    df['transplant_date'] = df['mrn'].map(liver_dict).combine_first(df['mrn'].map(recip_dict)).combine_first(df['mrn'].map(donor_dict))
    visit_dt = pd.to_datetime(df['visit_datetime'], errors='coerce')
    tx_dt = pd.to_datetime(df['transplant_date'], errors='coerce')
    df['days'] = (visit_dt - tx_dt).dt.days
    df.loc[tx_dt.isna(), 'patient_type'] = 'pre'
    df.loc[tx_dt.notna() & (df['days'] <= 0), 'patient_type'] = 'pre'
    df.loc[tx_dt.notna() & (df['days'] > 0), 'patient_type'] = 'post'
    r_d_lower = df['r_d'].fillna('').str.lower()
    liver_status_lower = df['liver_status'].fillna('').str.lower()
    is_hepatology = liver_status_lower.str.contains('hepatology|hepatitis|new patients', na=False)
    is_liver_context = r_d_lower.str.contains('liver', na=False)
    is_post = df['patient_type'] == 'post'
    is_pre = df['patient_type'] == 'pre'
    is_nephrology = r_d_lower.str.contains('nephrology', na=False)
    is_kidney_context = df['r_d'].notna() & ~is_liver_context & ~is_nephrology
    conditions = [is_hepatology, is_liver_context & is_post, is_liver_context & is_pre, is_nephrology, is_kidney_context & is_post, is_kidney_context & is_pre]
    choices = ['Hepatology', 'Post-Liver Tx', 'Pre-Liver Tx', 'Nephrology', 'Post-Kidney Tx', 'Pre-Kidney Tx']
    df['patient_type'] = np.select(conditions, choices, default='Pre-Kidney Tx')
    liver_age_dict = liver_df[['r_mrn', 'age_group']].dropna(subset=['r_mrn']).set_index('r_mrn')['age_group'].to_dict()
    recip_age_dict = kidney_rec_df[['r_mrn', 'age_group']].dropna(subset=['r_mrn']).set_index('r_mrn')['age_group'].to_dict()
    donor_age_dict = kidney_donor_df[['d_mrn', 'age_group_d']].dropna(subset=['d_mrn']).set_index('d_mrn')['age_group_d'].to_dict()
    df['age_group'] = df['mrn'].map(liver_age_dict).combine_first(df['mrn'].map(recip_age_dict)).combine_first(df['mrn'].map(donor_age_dict))
    hepatology_mask = df['patient_type'] == 'Hepatology'
    nephrology_mask = df['patient_type'] == 'Nephrology'
    df.loc[hepatology_mask, 'r_d'] = 'Liver Recipient'
    df.loc[nephrology_mask, 'r_d'] = 'Kidney Recipient'
    kidney_tx_mask = df['patient_type'].isin(['Post-Kidney Tx', 'Pre-Kidney Tx'])
    has_recipient = df['kidney_recipient'].notna()
    has_donor = df['kidney_donor'].notna()
    df.loc[kidney_tx_mask & has_recipient, 'r_d'] = 'Kidney Recipient'
    df.loc[kidney_tx_mask & ~has_recipient & has_donor, 'r_d'] = 'Kidney Donor'
    ambiguous_kidney = kidney_tx_mask & ~has_recipient & ~has_donor
    df.loc[ambiguous_kidney, 'need_review'] = 'yes'
    df['clinic_name'] = df['clinic_name'].astype(str).fillna('')
    clinic_lower = df['clinic_name'].str.lower()
    rd_lower = df['r_d'].fillna('').str.lower()
    df['clinic'] = pd.NA
    mask_kidney = clinic_lower.str.contains('renal|kidney', na=False)
    df.loc[mask_kidney, 'clinic'] = 'Kidney Tx'
    mask_liver_specific = clinic_lower.str.contains('pediatric liver transplant|adult pre liver transplant|adult post liver transplant', na=False)
    df.loc[mask_liver_specific & df['clinic'].isna(), 'clinic'] = 'liver Tx'
    mask_anesthesia = clinic_lower.str.contains('anesthesia', na=False)
    df.loc[mask_anesthesia & df['clinic'].isna(), 'clinic'] = pd.NA
    df.loc[mask_anesthesia & df['clinic'].isna() & rd_lower.str.contains('kidney'), 'clinic'] = 'Anesthesia-Kidney'
    df.loc[mask_anesthesia & df['clinic'].isna() & rd_lower.str.contains('liver'), 'clinic'] = 'Anesthesia-Liver'
    mask_urology = clinic_lower.str.contains('transplant urology|transplant cystoscopy clinic', na=False)
    df.loc[mask_urology & df['clinic'].isna(), 'clinic'] = 'Urology'
    mask_nutrition = clinic_lower.str.contains('clinical nutrition', na=False)
    df.loc[mask_nutrition & df['clinic'].isna(), 'clinic'] = 'Nutrition'
    mask_dressing = clinic_lower.str.contains('transplant dressing (procedure)', regex=False, na=False)
    df.loc[mask_dressing & df['clinic'].isna(), 'clinic'] = 'Surgery-Dressing'
    mask_surgery = clinic_lower.str.contains('transplant surgery', na=False)
    df.loc[mask_surgery & df['clinic'].isna(), 'clinic'] = 'Surgery-Liver'
    df.loc[mask_surgery & df['clinic'].isna() & rd_lower.str.contains('kidney'), 'clinic'] = 'Surgery-Kidney'
    mask_psych = clinic_lower.str.contains('psychology', na=False)
    df.loc[mask_psych & df['clinic'].isna(), 'clinic'] = 'Psychology'
    mask_social = clinic_lower.str.contains('social work', na=False)
    df.loc[mask_social & df['clinic'].isna(), 'clinic'] = 'Social Work'
    ALLOWED_VISIT_TYPES = {'FOLLOW UP', 'NEW', 'V FOLLOW UP', 'VV'}
    ref = pd.read_excel(historical_visits_file)
    df['visit_type'] = df['visit_type'].astype(str).str.strip()
    df.loc[df['visit_type'].str.lower().isin(['follow up', 'follow-up', 'followup']), 'visit_type'] = 'FOLLOW UP'
    df.loc[df['visit_type'].str.lower() == 'new', 'visit_type'] = 'NEW'
    df['visit_type'] = df['visit_type'].str.upper().str.strip()
    df['clinic_std'] = df['clinic'].astype(str).str.strip().str.upper()
    ref['clinic_std'] = ref['clinic'].astype(str).str.strip().str.upper()
    df['mrn_std'] = df['mrn'].astype(str).str.strip()
    ref['mrn_std'] = ref['MRN'].astype(str).str.strip()
    needs_reclass = ~df['visit_type'].isin(ALLOWED_VISIT_TYPES)
    ref_pairs = ref[['clinic_std', 'mrn_std']].drop_duplicates()
    tmp = df.loc[needs_reclass, ['clinic_std', 'mrn_std']].merge(ref_pairs.assign(seen_in_ref=True), on=['clinic_std', 'mrn_std'], how='left')
    df.loc[needs_reclass, 'visit_type'] = np.where(tmp['seen_in_ref'].notna(), 'FOLLOW UP', 'NEW')
    unexpected_mask = ~df['visit_type'].isin(ALLOWED_VISIT_TYPES)
    unexpected_values = df.loc[unexpected_mask, 'visit_type'].unique()
    if len(unexpected_values) > 0:
        df.loc[unexpected_mask, 'need_review'] = 'yes'
        if 'original_visit_type' not in df.columns:
            df['original_visit_type'] = df['visit_type'].copy()
    df['visit_datetime'] = pd.to_datetime(df['visit_datetime'], errors='coerce')
    df = df.sort_values(['mrn', 'clinic', 'visit_datetime'], kind='mergesort').reset_index(drop=True)
    df['is_first_visit'] = df.groupby(['mrn', 'clinic']).cumcount() == 0
    df['group_size'] = df.groupby(['mrn', 'clinic'])['visit_type'].transform('size')
    df['all_new'] = (df.groupby(['mrn', 'clinic'])['visit_type'].transform('nunique') == 1) & df['visit_type'].eq('NEW')
    mask_to_change = (df['group_size'] > 1) & df['all_new'] & ~df['is_first_visit']
    changed_examples = df.loc[mask_to_change].copy()
    df.loc[mask_to_change, 'visit_type'] = 'FOLLOW UP'
    df = df.drop(columns=['is_first_visit', 'group_size', 'all_new'])
    export_df = df.rename(columns={'visit_datetime': 'date', 'patengname': 'name', 'age_group': 'age', 'patient_type': 'patient type', 'visit_type': 'visit type', 'r_d': 'r/d', 'clinic_name': 'Medica - Plus Clinic Name', 'mrp': 'Consultant name from Medica +'})
    final_cols = ['date', 'mrn', 'name', 'age', 'patient type', 'clinic', 'visit type', 'r/d', 'Medica - Plus Clinic Name', 'Consultant name from Medica +', 'need_review']
    export_df = export_df[final_cols].copy()
    export_df['date'] = pd.to_datetime(export_df['date'], errors='coerce').dt.date
    return export_df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opd", required=True, help="Outpatient visits Excel file")
    parser.add_argument("--liver", required=True, help="Liver registry Excel file")
    parser.add_argument("--kidney-recipient", required=True)
    parser.add_argument("--kidney-donor", required=True)
    parser.add_argument("--history", required=True, help="Historical visits Excel file")
    parser.add_argument("--output", required=True, help="Destination Excel file")
    args = parser.parse_args()
    report = prepare_report(
        args.opd, args.liver, args.kidney_recipient,
        args.kidney_donor, args.history,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.to_excel(output, index=False)
    print(f"Exported: {output}")


if __name__ == "__main__":
    main()
