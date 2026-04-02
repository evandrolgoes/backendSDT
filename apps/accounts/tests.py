from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Invitation, Tenant, User
from apps.clients.models import EconomicGroup, SubGroup
from apps.physical.models import PhysicalSale


class UserScopeFlowTests(TestCase):
    def setUp(self):
        self.admin_tenant = Tenant.objects.create(name="Administradores", slug="admin")
        self.client_tenant = Tenant.objects.create(name="Cliente", slug="cliente")
        self.user_tenant = Tenant.objects.create(name="Usuarios", slug="usuario")

        self.admin_user = User.objects.create_user(
            username="admin_owner",
            email="admin@example.com",
            password="secret123",
            full_name="Admin Sistema",
            tenant=self.admin_tenant,
            role=User.Role.OWNER,
        )
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="secret123",
            full_name="Owner Cliente",
            tenant=self.client_tenant,
            role=User.Role.OWNER,
        )
        self.superuser = User.objects.create_superuser(
            username="root",
            email="root@example.com",
            password="secret123",
        )

        self.group_a = EconomicGroup.objects.create(tenant=self.client_tenant, grupo="Grupo A")
        self.group_b = EconomicGroup.objects.create(tenant=self.client_tenant, grupo="Grupo B")
        self.subgroup_a = SubGroup.objects.create(tenant=self.client_tenant, grupo=self.group_a, subgrupo="Subgrupo A")
        self.subgroup_b = SubGroup.objects.create(tenant=self.client_tenant, grupo=self.group_b, subgrupo="Subgrupo B")

        self.api_client = APIClient()

    def test_invitation_accept_copies_scope_assignments_to_user(self):
        self.api_client.force_authenticate(user=self.owner)

        response = self.api_client.post(
            "/api/admin-invitations/",
            {
                "full_name": "Convidado Escopado",
                "email": "scope@example.com",
                "access_status": User.AccessStatus.ACTIVE,
                "assigned_groups": [self.group_a.id],
                "assigned_subgroups": [self.subgroup_a.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)

        invitation = Invitation.objects.get(email="scope@example.com")
        self.assertSetEqual(set(invitation.assigned_groups.values_list("id", flat=True)), {self.group_a.id})
        self.assertSetEqual(set(invitation.assigned_subgroups.values_list("id", flat=True)), {self.subgroup_a.id})

        accept_response = APIClient().post(
            f"/api/auth/invitations/{invitation.token}/accept/",
            {
                "full_name": "Convidado Escopado",
                "username": "convidado_escopado",
                "password": "secret123",
                "password_confirm": "secret123",
            },
            format="json",
        )

        self.assertEqual(accept_response.status_code, 201, accept_response.data)

        invited_user = User.objects.get(email="scope@example.com")
        self.assertEqual(invited_user.tenant, self.user_tenant)
        self.assertEqual(invited_user.master_user, self.owner)
        self.assertSetEqual(set(invited_user.assigned_groups.values_list("id", flat=True)), {self.group_a.id})
        self.assertSetEqual(set(invited_user.assigned_subgroups.values_list("id", flat=True)), {self.subgroup_a.id})

    def test_managed_user_is_visible_and_editable_in_users_app(self):
        managed_user = User.objects.create_user(
            username="managed_user",
            email="managed@example.com",
            password="secret123",
            full_name="Usuario Gerenciado",
            tenant=self.user_tenant,
            master_user=self.owner,
            role=User.Role.STAFF,
        )

        self.api_client.force_authenticate(user=self.owner)

        list_response = self.api_client.get("/api/users/")
        self.assertEqual(list_response.status_code, 200, list_response.data)
        listed_ids = {item["id"] for item in list_response.data["results"]}
        self.assertIn(managed_user.id, listed_ids)

        patch_response = self.api_client.patch(
            f"/api/users/{managed_user.id}/",
            {
                "assigned_groups": [self.group_a.id],
                "assigned_subgroups": [self.subgroup_a.id],
            },
            format="json",
        )

        self.assertEqual(patch_response.status_code, 200, patch_response.data)

        managed_user.refresh_from_db()
        self.assertSetEqual(set(managed_user.assigned_groups.values_list("id", flat=True)), {self.group_a.id})
        self.assertSetEqual(set(managed_user.assigned_subgroups.values_list("id", flat=True)), {self.subgroup_a.id})

    def test_managed_user_without_wallet_returns_master_user_error_before_group_scope_error(self):
        managed_user = User.objects.create_user(
            username="walletless_user",
            email="walletless@example.com",
            password="secret123",
            full_name="Usuario Sem Carteira",
            tenant=self.user_tenant,
            role=User.Role.STAFF,
        )

        self.api_client.force_authenticate(user=self.superuser)
        response = self.api_client.patch(
            f"/api/users/{managed_user.id}/",
            {
                "tenant": self.user_tenant.id,
                "assigned_groups": [self.group_a.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("master_user", response.data)
        self.assertNotIn("assigned_groups", response.data)

    def test_non_admin_user_cannot_manage_users_from_another_wallet_in_same_tenant(self):
        other_owner = User.objects.create_user(
            username="other_owner",
            email="other_owner@example.com",
            password="secret123",
            full_name="Outro Owner",
            tenant=self.client_tenant,
            role=User.Role.OWNER,
        )

        self.api_client.force_authenticate(user=self.owner)

        list_response = self.api_client.get("/api/users/")
        self.assertEqual(list_response.status_code, 200, list_response.data)
        listed_ids = {item["id"] for item in list_response.data["results"]}
        self.assertNotIn(other_owner.id, listed_ids)

        patch_response = self.api_client.patch(
            f"/api/users/{other_owner.id}/",
            {"full_name": "Nao deveria editar"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 404, patch_response.data)

    def test_admin_tenant_user_can_manage_users_from_any_wallet(self):
        external_user = User.objects.create_user(
            username="external_user",
            email="external@example.com",
            password="secret123",
            full_name="Usuario Externo",
            tenant=self.user_tenant,
            master_user=self.owner,
            role=User.Role.STAFF,
        )

        self.api_client.force_authenticate(user=self.admin_user)

        list_response = self.api_client.get("/api/users/")
        self.assertEqual(list_response.status_code, 200, list_response.data)
        listed_ids = {item["id"] for item in list_response.data["results"]}
        self.assertIn(external_user.id, listed_ids)
        self.assertIn(self.owner.id, listed_ids)

        patch_response = self.api_client.patch(
            f"/api/users/{external_user.id}/",
            {"full_name": "Usuario Editado Pelo Admin"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200, patch_response.data)

        external_user.refresh_from_db()
        self.assertEqual(external_user.full_name, "Usuario Editado Pelo Admin")

    def test_admin_invitation_for_usuario_uses_wallet_scope_for_groups(self):
        self.api_client.force_authenticate(user=self.admin_user)

        response = self.api_client.post(
            "/api/admin-invitations/",
            {
                "target_tenant_slug": "usuario",
                "master_user": self.owner.id,
                "full_name": "Convidado Admin",
                "email": "admin.scope@example.com",
                "access_status": User.AccessStatus.ACTIVE,
                "assigned_groups": [self.group_a.id],
                "assigned_subgroups": [self.subgroup_a.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)

        invitation = Invitation.objects.get(email="admin.scope@example.com")
        self.assertEqual(invitation.master_user, self.owner)
        self.assertSetEqual(set(invitation.assigned_groups.values_list("id", flat=True)), {self.group_a.id})
        self.assertSetEqual(set(invitation.assigned_subgroups.values_list("id", flat=True)), {self.subgroup_a.id})

    def test_scoped_user_only_sees_allowed_groups_subgroups_and_sales(self):
        scoped_user = User.objects.create_user(
            username="scoped_user",
            email="scoped@example.com",
            password="secret123",
            full_name="Usuario Escopado",
            tenant=self.user_tenant,
            master_user=self.owner,
            role=User.Role.STAFF,
        )
        scoped_user.assigned_subgroups.add(self.subgroup_a)

        allowed_sale = PhysicalSale.objects.create(
            tenant=self.client_tenant,
            created_by=self.owner,
            grupo=self.group_a,
            subgrupo=self.subgroup_a,
            cultura_produto="Soja",
        )
        PhysicalSale.objects.create(
            tenant=self.client_tenant,
            created_by=self.owner,
            grupo=self.group_b,
            subgrupo=self.subgroup_b,
            cultura_produto="Milho",
        )

        self.api_client.force_authenticate(user=scoped_user)

        groups_response = self.api_client.get("/api/groups/")
        self.assertEqual(groups_response.status_code, 200, groups_response.data)
        self.assertEqual([item["id"] for item in groups_response.data["results"]], [self.group_a.id])

        subgroups_response = self.api_client.get("/api/subgroups/")
        self.assertEqual(subgroups_response.status_code, 200, subgroups_response.data)
        self.assertEqual([item["id"] for item in subgroups_response.data["results"]], [self.subgroup_a.id])

        sales_response = self.api_client.get("/api/physical-sales/")
        self.assertEqual(sales_response.status_code, 200, sales_response.data)
        self.assertEqual([item["id"] for item in sales_response.data["results"]], [allowed_sale.id])

    def test_admin_invitation_cannot_be_edited_after_creation(self):
        invitation = Invitation.objects.create(
            tenant=self.client_tenant,
            kind=Invitation.Kind.PLATFORM_ADMIN,
            target_tenant_name=self.user_tenant.name,
            target_tenant_slug=self.user_tenant.slug,
            email="locked@example.com",
            invited_by=self.owner,
        )

        self.api_client.force_authenticate(user=self.owner)
        response = self.api_client.patch(
            f"/api/admin-invitations/{invitation.id}/",
            {"full_name": "Nao pode editar"},
            format="json",
        )

        self.assertEqual(response.status_code, 405, response.data)

    def test_only_superuser_can_delete_admin_invitation(self):
        invitation = Invitation.objects.create(
            tenant=self.client_tenant,
            kind=Invitation.Kind.PLATFORM_ADMIN,
            target_tenant_name=self.user_tenant.name,
            target_tenant_slug=self.user_tenant.slug,
            email="delete-me@example.com",
            invited_by=self.owner,
        )

        self.api_client.force_authenticate(user=self.owner)
        forbidden_response = self.api_client.delete(f"/api/admin-invitations/{invitation.id}/")
        self.assertEqual(forbidden_response.status_code, 403, forbidden_response.data)
        self.assertTrue(Invitation.objects.filter(id=invitation.id).exists())

        self.api_client.force_authenticate(user=self.superuser)
        allowed_response = self.api_client.delete(f"/api/admin-invitations/{invitation.id}/")
        self.assertEqual(allowed_response.status_code, 204, allowed_response.data)
        self.assertFalse(Invitation.objects.filter(id=invitation.id).exists())
