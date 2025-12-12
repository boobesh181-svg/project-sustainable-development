"""Fixed MRV service for handling sample tracking, tests, and chain of custody."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mrv.models import (
    MRVSample, MRVTest, Lab, ChainStep, MRVEventLog, MRVSampleStatus
)


class MRVServiceFixed:
    """Fixed service for MRV operations."""
    
    @staticmethod
    async def get_mrv_stats(db: AsyncSession) -> Dict[str, Any]:
        """Get MRV statistics."""
        # Sample stats
        sample_result = await db.execute(select(MRVSample))
        all_samples = sample_result.scalars().all()
        total_samples = len(all_samples)
        
        samples_by_status = {}
        for sample in all_samples:
            status = sample.status.value
            samples_by_status[status] = samples_by_status.get(status, 0) + 1
        
        # Test stats
        test_result = await db.execute(select(MRVTest))
        all_tests = test_result.scalars().all()
        total_tests = len(all_tests)
        
        tests_by_parameter = {}
        passed_tests = 0
        for test in all_tests:
            param = test.parameter
            tests_by_parameter[param] = tests_by_parameter.get(param, 0) + 1
            if test.passed:
                passed_tests += 1
        
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Lab count
        lab_result = await db.execute(select(Lab))
        all_labs = lab_result.scalars().all()
        active_labs = len(all_labs)
        
        return {
            "total_samples": total_samples,
            "samples_by_status": samples_by_status,
            "total_tests": total_tests,
            "tests_by_parameter": tests_by_parameter,
            "pass_rate": pass_rate,
            "active_labs": active_labs,
        }
