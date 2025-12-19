import {
  EngagementEvents,
  RefactoringCommandUsedPayload,
} from "@saili/common-all";

export class ProxyMetricUtils {
  static trackRefactoringProxyMetric(opts: {
    props: RefactoringCommandUsedPayload;
    extra: {
      [key: string]: any;
    };
  }) {
    const { props, extra } = opts;
    const payload = {
      ...props,
      ...extra,
    };
  }
}
