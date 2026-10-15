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
        from tractography.wma import _wma_output_contract_error
        return _wma_output_contract_error(summary)
    except (TypeError, ValueError, KeyError, AttributeError):
        return 'Malformed bundle QC; revalidation required'
