<template>
  <div
    :class="isExpanded ? 'w-[220px]' : 'w-[50px]'"
    class="border-r bg-gray-50 relative hidden sm:flex h-screen flex-col justify-start duration-300 ease-in-out p-2"
  >
    <PrimaryDropDown :is-expanded="isExpanded" />
    <div
      class="mt-2.5"
      :class="!isExpanded ? 'flex flex-col items-start' : ''"
      ondragstart="return false;"
      ondrop="return false;"
    >
      <SidebarItem
        label="Search"
        class="mb-1"
        :is-collapsed="!isExpanded"
        @click="() => emitter.emit('showSearchPopup', true)"
      >
        <template #icon>
          <LucideSearch class="size-4" />
        </template>
        <template #right>
          <div
            class="flex items-center justify-start w-full duration-300 ease-in-out"
            :class="
              isExpanded ? 'ml-2 opacity-100' : 'ml-0 overflow-hidden opacity-0'
            "
          ></div>
        </template>
      </SidebarItem>
      <SidebarItem
        :icon="sidebarItems[0].icon"
        :label="sidebarItems[0].label"
        :to="sidebarItems[0].route"
        :is-collapsed="!isExpanded"
        class="mb-0.5"
      />
      <SidebarItem
        :label="'Inbox'"
        icon="inbox"
        class="mb-0.5"
        :is-collapsed="!isExpanded"
        :to="'/t/' + team + '/notifications'"
      >
        <template #right>
          <div
            v-if="isExpanded && notifCount.data > 0"
            class="flex items-center justify-start w-full duration-300 ease-in-out ml-2"
          >
            <span class="text-sm text-gray-500 ease-in ml-auto">
              {{ notifCount.data }}
            </span>
          </div>
        </template>
      </SidebarItem>
      <SidebarItem
        v-for="item in sidebarItems.slice(1)"
        :key="item.label"
        :icon="item.icon"
        :label="item.label"
        :to="item.route"
        :is-collapsed="!isExpanded"
        class="mb-0.5"
      />
    </div>
    <div class="mt-auto">
      <StorageBar :is-expanded="isExpanded" />
      <SidebarItem
        :label="!isExpanded ? 'Expand' : 'Collapse'"
        :is-collapsed="!isExpanded"
        class="mt-auto py-4"
        @click="toggleExpanded"
      >
        <template #icon>
          <span class="grid h-4.5 w-4.5 flex-shrink-0 place-items-center">
            <ArrowLeftFromLine
              class="stroke-[1.5] h-4 w-4 text-gray-700 duration-300 ease-in-out"
              :class="{ '[transform:rotateY(180deg)]': !isExpanded }"
            />
          </span>
        </template>
      </SidebarItem>
    </div>
  </div>
</template>
<script setup>
import PrimaryDropDown from "./PrimaryDropdown.vue"
import { ArrowLeftFromLine } from "lucide-vue-next"
import Recent from "./EspressoIcons/Recent.vue"
import Star from "./EspressoIcons/Star.vue"
import Home from "./EspressoIcons/Home.vue"
import Trash from "./EspressoIcons/Trash.vue"
import SidebarItem from "@/components/SidebarItem.vue"
import Team from "./EspressoIcons/Organization.vue"
import StorageBar from "./StorageBar.vue"
import { notifCount } from "@/resources/permissions"
import { computed } from "vue"
import { useStore } from "vuex"
import Users from "./EspressoIcons/Users.vue"
import { useRoute } from "vue-router"
import { getTeams } from "../resources/files"

defineEmits(["toggleMobileSidebar", "showSearchPopUp"])
const store = useStore()
const route = useRoute()
notifCount.fetch()

const isExpanded = computed(() => store.state.IsSidebarExpanded)
const team = computed(
  () => route.params.team || localStorage.getItem("recentTeam")
)

const sidebarItems = computed(() => {
  const items = [
    {
      label: "Home",
      route: `/t/${team.value}/`,
      icon: Home,
    },
    {
      label: "Recents",
      route: `/t/${team.value}/recents`,
      icon: Recent,
    },
    {
      label: "Favourites",
      route: `/t/${team.value}/favourites`,
      icon: Star,
    },
    {
      label: "Team",
      route: `/t/${team.value}/team`,
      icon: Team,
    },
    {
      label: "Shared",
      route: `/shared/`,
      icon: Users,
    },
    {
      label: "Trash",
      route: `/t/${team.value}/trash`,
      icon: Trash,
    },
  ]
  if (getTeams.data && getTeams.data[team.value]?.title === "Your Drive")
    items.splice(1, 1)
  return items
})

const toggleExpanded = () =>
  store.commit("setIsSidebarExpanded", isExpanded.value ? false : true)
</script>
