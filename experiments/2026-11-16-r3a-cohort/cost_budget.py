"""Planning-only extrapolations from completed batches, not runtime guarantees."""
import json
import math
from pathlib import Path
import statistics
import driver

BASE=Path(__file__).resolve().parent


def main():
    with driver.protocol_lock():
        summary=driver.read(BASE/'summary.json');attempts=[]
        for p in sorted((BASE/'batches').glob('*/attempt*.json')):
            a=driver.read(p)
            if a['status']=='complete':attempts.append(a)
        full=[a for a in attempts if len(a['cases'])==8];walls=[a['seconds'] for a in full]
        rows=[r for r in summary['cases'] if r.get('driver_seconds') is not None]
        cases_seconds=[r['driver_seconds'] for r in rows];pending=summary['pending'];blocks=math.ceil(pending/8)
        mean_wall=statistics.mean(walls);mean_case=statistics.mean(cases_seconds)
        result=dict(planning_only=True,started=summary['started'],remaining=pending,full_batches=len(full),
            observed_batch_seconds=walls,remaining_blocks=blocks,
            block_schedule_hours=dict(mean=blocks*mean_wall/3600,observed_min=blocks*min(walls)/3600,
                observed_max=blocks*max(walls)/3600),
            pooled_case_time_divided_by_8_hours=pending*mean_case/8/3600,
            pooled_note='An optimistic work-conversion reference for a continuously occupied 8-worker queue, not a bound or a prediction; the frozen driver does not use this schedule.',
            by_tau={str(t):dict(cases=len(v),mean_case_seconds=statistics.mean(v),max_case_seconds=max(v))
                for t in range(1,10) if (v:=[r['driver_seconds'] for r in rows if r['case'].startswith(f'tau{t}-')])},
            caveats=['Only a small prefix of the frozen cohort has been observed.',
                'The remaining task mix, convergence paths and timeouts differ.',
                'Batch tails leave workers idle; phase walltimes are not CPU time.',
                'Verification, agent work and documentation outside the driver are additional.',
                'No scheduling or numerical setting was changed for this calculation.'])
        driver.write(BASE/'cost-estimate.json',result)
        (BASE/'cost-estimate.md').write_text(f"# 現時点の費用見積もり\n\n実行{summary['started']}、未実行{pending}。"+
            f"現在の8件区切りを単純に延長すると残り約{result['block_schedule_hours']['mean']:.1f}時間、"+
            f"観測バッチの最小/最大を使った目安は{result['block_schedule_hours']['observed_min']:.1f}〜{result['block_schedule_hours']['observed_max']:.1f}時間。\n\n"+
            f"ケース壁時計の合計を8 workerへ換算した参考値は約{result['pooled_case_time_divided_by_8_hours']:.1f}時間。"+
            "これは継続的な8 worker配置を仮定する楽観的な作業量換算であり、実測の予測や下界ではない。固定driverのスケジュールは変えていない。\n\n"+
            "入力/収束/時間切れ、バッチ末尾の遊休、起動/検証/文書作業へ依存する。少数バッチからの外挿で、完走時間を保証しない。\n"+
            "原因診断に900件完走は必須ではなく、ユーザーの選好により、追加バッチより少数例の不収束/費用診断を優先する。\n")
        print(json.dumps(result,indent=2))


if __name__=='__main__':main()
