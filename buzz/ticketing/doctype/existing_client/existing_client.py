# Copyright (c) 2026, BWH Studios and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ExistingClient(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		email: DF.Data
		first_name: DF.Data
		last_name: DF.Data | None
		phone: DF.Data
	# end: auto-generated types

	def before_save(self):
		if self.email:
			self.email = self.email.strip().lower()
		if self.phone:
			self.phone = self.phone.strip()
