from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Invitation, Tenant, User
from apps.anotacoes.models import Anotacao
from apps.clients.models import EconomicGroup, SubGroup


class UserFlowTests(TestCase):
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

        self.api_client = APIClient()

    def test_invitation_accept_creates_user_without_scope_assignments(self):
        self.api_client.force_authenticate(user=self.owner)

        response = self.api_client.post(
            "/api/admin-invitations/",
            {
                "full_name": "Convidado",
                "email": "invite@example.com",
                "access_status": User.AccessStatus.ACTIVE,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)

        invitation = Invitation.objects.get(email="invite@example.com")
        accept_response = APIClient().post(
            f"/api/auth/invitations/{invitation.token}/accept/",
            {
                "full_name": "Convidado",
                "username": "convidado",
                "password": "secret123",
                "password_confirm": "secret123",
            },
            format="json",
        )

        self.assertEqual(accept_response.status_code, 201, accept_response.data)

        invited_user = User.objects.get(email="invite@example.com")
        self.assertEqual(invited_user.tenant, self.user_tenant)
        self.assertEqual(invited_user.master_user, self.owner)

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
            {"full_name": "Usuario Atualizado"},
            format="json",
        )

        self.assertEqual(patch_response.status_code, 200, patch_response.data)

        managed_user.refresh_from_db()
        self.assertEqual(managed_user.full_name, "Usuario Atualizado")

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


class GroupPrivacyScopeTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Cliente Privado", slug="cliente-privado")
        self.user = User.objects.create_user(
            username="scoped_user",
            email="scoped@example.com",
            password="secret123",
            full_name="Scoped User",
            tenant=self.tenant,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.allowed_group = EconomicGroup.objects.create(tenant=self.tenant, grupo="Grupo Permitido")
        self.blocked_group = EconomicGroup.objects.create(tenant=self.tenant, grupo="Grupo Bloqueado")
        self.allowed_subgroup = SubGroup.objects.create(tenant=self.tenant, grupo=self.allowed_group, subgrupo="Subgrupo Permitido")
        self.blocked_subgroup = SubGroup.objects.create(tenant=self.tenant, grupo=self.blocked_group, subgrupo="Subgrupo Bloqueado")

        self.user.accessible_groups.set([self.allowed_group])
        self.user.accessible_subgroups.set([self.allowed_subgroup])

    def test_group_and_subgroup_endpoints_only_return_records_with_user_access(self):
        group_response = self.client.get("/api/groups/")
        self.assertEqual(group_response.status_code, 200, group_response.data)
        self.assertEqual([item["id"] for item in group_response.data["results"]], [self.allowed_group.id])

        subgroup_response = self.client.get("/api/subgroups/")
        self.assertEqual(subgroup_response.status_code, 200, subgroup_response.data)
        self.assertEqual([item["id"] for item in subgroup_response.data["results"]], [self.allowed_subgroup.id])

    def test_dashboard_filter_is_sanitized_against_user_scope(self):
        self.user.dashboard_filter = {
            "grupo": [str(self.allowed_group.id), str(self.blocked_group.id)],
            "subgrupo": [str(self.allowed_subgroup.id), str(self.blocked_subgroup.id)],
            "cultura": [],
            "safra": [],
        }
        self.user.save(update_fields=["dashboard_filter"])

        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["dashboard_filter"]["grupo"], [str(self.allowed_group.id)])
        self.assertEqual(response.data["dashboard_filter"]["subgrupo"], [str(self.allowed_subgroup.id)])

    def test_many_to_many_group_and_subgroup_payloads_are_trimmed(self):
        anotacao = Anotacao.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            modificado_por=self.user,
            titulo="Nota privada",
        )
        anotacao.grupos.set([self.allowed_group, self.blocked_group])
        anotacao.subgrupos.set([self.allowed_subgroup, self.blocked_subgroup])

        response = self.client.get("/api/anotacoes/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["results"]), 1)
        row = response.data["results"][0]
        self.assertEqual(row["grupos"], [self.allowed_group.id])
        self.assertEqual(row["subgrupos"], [self.allowed_subgroup.id])

    def test_usuario_tenant_user_keeps_group_scope_from_access_lists_even_with_different_tenant(self):
        usuario_tenant = Tenant.objects.create(name="Usuarios", slug="usuario")
        carteira_user = User.objects.create_user(
            username="carteira_scope",
            email="carteira_scope@example.com",
            password="secret123",
            full_name="Carteira Scope",
            tenant=self.tenant,
            role=User.Role.OWNER,
        )
        usuario = User.objects.create_user(
            username="usuario_scope",
            email="usuario_scope@example.com",
            password="secret123",
            full_name="Usuario Scope",
            tenant=usuario_tenant,
            master_user=carteira_user,
            role=User.Role.STAFF,
        )
        usuario.accessible_groups.set([self.allowed_group])
        usuario.accessible_subgroups.set([self.allowed_subgroup])

        client = APIClient()
        client.force_authenticate(user=usuario)

        group_response = client.get("/api/groups/")
        self.assertEqual(group_response.status_code, 200, group_response.data)
        self.assertEqual([item["id"] for item in group_response.data["results"]], [self.allowed_group.id])

        subgroup_response = client.get("/api/subgroups/")
        self.assertEqual(subgroup_response.status_code, 200, subgroup_response.data)
        self.assertEqual([item["id"] for item in subgroup_response.data["results"]], [self.allowed_subgroup.id])
