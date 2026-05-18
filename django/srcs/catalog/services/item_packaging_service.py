"""
ItemPackaging Service

Business logic for Item Packaging operations.
"""

from catalog.models import ItemPackaging


class ItemPackagingService:

    @staticmethod
    def get_active_for_item(item):
        """
        Return active (non-deleted) packagings for an item.
        """
        return item.packagings.filter(is_deleted=False).order_by('quantity')

    @staticmethod
    def _validate_name(item, name: str, exclude_id=None) -> str:
        """
        Validate packaging name is unique for an item (case-insensitive).

        Returns: cleaned name if valid, raises ValueError if invalid.
        """
        name_strip = name.strip()
        if not name_strip:
            raise ValueError("Packaging name cannot be empty")

        qs = item.packagings.filter(is_deleted=False, name__iexact=name_strip)
        if exclude_id is not None:
            qs = qs.exclude(id=exclude_id)

        if qs.exists():
            raise ValueError("Packaging name already exists for this item")
        
        return name_strip

    @staticmethod
    def create(*, item, name, quantity, user, barcode='', note='', status=ItemPackaging.Status.ACTIVE):
        """
        Create a new packaging unit for an item.
        """
        if quantity is None or int(quantity) <= 0:
            raise ValueError("Quantity must be greater than zero")

        name_clean = ItemPackagingService._validate_name(item, name)

        packaging = ItemPackaging(
            item=item,
            name=name_clean,
            quantity=int(quantity),
            barcode=barcode.strip() if barcode else '',
            note=note.strip() if note else '',
            status=status,
            created_by=user
        )
        packaging.full_clean()
        packaging.save()
        return packaging

    @staticmethod
    def update(packaging, *, user, **fields):
        """
        Update an existing packaging unit.
        """
        allowed_fields = {'name', 'quantity', 'barcode', 'note', 'status'}

        if 'name' in fields:
            fields['name'] = ItemPackagingService._validate_name(packaging.item, fields['name'], exclude_id=packaging.id)

        if 'quantity' in fields:
            if fields['quantity'] is None or int(fields['quantity']) <= 0:
                raise ValueError("Quantity must be greater than zero")
            fields['quantity'] = int(fields['quantity'])

        if 'barcode' in fields and fields['barcode']:
            fields['barcode'] = fields['barcode'].strip()

        if 'note' in fields and fields['note']:
            fields['note'] = fields['note'].strip()

        for field, value in fields.items():
            if field in allowed_fields:
                setattr(packaging, field, value)

        packaging.updated_by = user
        packaging.full_clean()
        packaging.save()
        return packaging

    @staticmethod
    def delete(packaging, *, user):
        """
        Soft-delete a packaging unit.
        """
        packaging.delete(user=user)
