"""Revalidate recorded bundle QC before trusting legacy green run states."""


def bundle_record_error(product, record):
    if product not in {'bundles.wmql', 'bundles.wma'}:
        return None
    if record.get('automatic_qc_passed') is False:
        return record.get('error') or 'Recorded automatic QC failed'
    if record.get('status') not in {'completed', 'passed'}:
        return 'Bundle QC is missing or not completed'
    summary = record.get('output_summary') or {}
    try:
        if product == 'bundles.wmql':
            from tractography.wmql import WMQL_QC_VERSION, _wmql_output_contract_error
            if record.get('version') != WMQL_QC_VERSION or record.get('automatic_qc_passed') is not True:
                return 'Legacy WMQL QC must be revalidated under the query-snapshot and sampling policy'
            return _wmql_output_contract_error(summary, int(summary.get('bundle_count') or 0))
        from tractography.wma import WMA_QC_VERSION, _wma_output_contract_error, tract_sampling_eligibility
        error = _wma_output_contract_error(summary)
        if error:
            return error
        if record.get('version') != WMA_QC_VERSION or record.get('automatic_qc_passed') is not True:
            return 'Legacy WMA QC must be revalidated with per-tract sampling, not major tracts alone'
        counts = summary.get('anatomical_tract_streamline_counts') or {}
        if len(counts) != int(summary.get('anatomical_tract_count') or 0):
            return 'Missing per-tract WMA sampling counts; revalidation required'
        sampling = tract_sampling_eligibility(counts)
        if not sampling['all_tract_sampling_passed']:
            return 'WMA tracts have insufficient sampling: ' + ', '.join(sampling['excluded_from_quantification'])
        return None
    except (TypeError, ValueError, KeyError, AttributeError):
        return 'Malformed bundle QC; revalidation required'
