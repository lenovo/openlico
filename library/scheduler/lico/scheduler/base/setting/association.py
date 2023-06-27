# Copyright 2023-present Lenovo
# Confidential and Proprietary

from typing import List

import attr


@attr.s(slots=True)
class Association:
    account: str = attr.ib()
    qos: List[str] = attr.ib(factory=list)

    @classmethod
    def from_dict(cls, assoc_info_dict):
        return Association(
            # LICO billing group corresponds to SLURM account
            account=assoc_info_dict["billing_group"],
            qos=assoc_info_dict["limitations"]
        )
